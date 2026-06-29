import type { Express, Request, RequestHandler, Response } from "express";
import session from "express-session";
import createMemoryStore from "memorystore";
import { randomUUID, scryptSync, timingSafeEqual } from "crypto";
import fs from "fs";
import path from "path";
import z from "zod";
import { auditLogger, type AuditDetailsInput } from "../audit/logger";

const SESSION_COOKIE_NAME = "phantom.sid";
const SESSION_SECRET_ENV = "PHANTOM_SESSION_SECRET";
const LOGIN_WINDOW_MS = 10 * 60 * 1000;
const LOGIN_MAX_ATTEMPTS = 5;
const LOGIN_BLOCK_MS = 15 * 60 * 1000;

const operatorSeedSchema = z.object({
  username: z.string().min(1),
  password_hash: z.string().min(1),
  password_salt: z.string().min(1),
  hash_scheme: z.literal("scrypt"),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
  disabled: z.boolean().optional(),
});

type OperatorSeed = z.infer<typeof operatorSeedSchema>;

type OperatorSession = {
  username: string;
  authenticatedAt: string;
};

declare module "express-session" {
  interface SessionData {
    operator?: OperatorSession;
  }
}

type RateLimitEntry = {
  attempts: number[];
  blockedUntil: number;
};

type RateLimitResult =
  | { allowed: true; retryAfterMs: 0 }
  | { allowed: false; retryAfterMs: number };

export type AuthSessionResponse = {
  authenticated: boolean;
  username?: string;
  session_type: "session_cookie";
  setup_required?: boolean;
};

export type AuthService = {
  sessionMiddleware: RequestHandler;
  requireAuth: RequestHandler;
  attachSession: (req: Request) => Promise<void>;
  getSessionResponse: (req: Request) => AuthSessionResponse;
  auditProtectedAction: (
    eventType: string,
    detailsFactory?: (req: Request, res: Response) => AuditDetailsInput | undefined,
  ) => RequestHandler;
  isPublicHealthSafe: () => boolean;
};

const MemoryStore = createMemoryStore(session);
const rateLimitState = new Map<string, RateLimitEntry>();
let cachedOperator: OperatorSeed | null = null;
let operatorLoadError: Error | null = null;

function isProduction() {
  return process.env.NODE_ENV === "production";
}

function getOperatorSeedPath() {
  return process.env.PHANTOM_OPERATOR_SEED_PATH || path.resolve("data", "operator.json");
}

function getSessionSecret() {
  const secret = process.env[SESSION_SECRET_ENV];
  if (secret) {
    return secret;
  }

  if (isProduction()) {
    throw new Error(`Missing required ${SESSION_SECRET_ENV} in production`);
  }

  console.warn(`[AUTH] ${SESSION_SECRET_ENV} not set. Using development fallback secret.`);
  return "phantom-scan-dev-only-secret";
}

function loadOperatorSeed(): OperatorSeed {
  const operatorSeedPath = getOperatorSeedPath();
  let raw: string;
  try {
    raw = fs.readFileSync(operatorSeedPath, "utf-8");
  } catch (error) {
    throw new Error(`[AUTH] Operator seed file missing or unreadable at ${operatorSeedPath}: ${String(error)}`);
  }

  let parsed: unknown;
  try {
    parsed = parseOperatorSeedJson(raw);
  } catch (error) {
    throw new Error(`[AUTH] Operator seed file is malformed JSON at ${operatorSeedPath}: ${String(error)}`);
  }

  const result = operatorSeedSchema.safeParse(parsed);
  if (!result.success) {
    throw new Error(
      `[AUTH] Operator seed file is malformed at ${operatorSeedPath}: ${result.error.issues
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ")}`,
    );
  }

  return result.data;
}

function parseOperatorSeedJson(raw: string) {
  try {
    return JSON.parse(raw);
  } catch {
    const firstBrace = raw.indexOf("{");
    const lastBrace = raw.lastIndexOf("}");
    if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) {
      throw new Error("No JSON object found in operator seed file");
    }
    return JSON.parse(raw.slice(firstBrace, lastBrace + 1));
  }
}

function ensureOperatorSeedDir() {
  const directory = path.dirname(getOperatorSeedPath());
  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, { recursive: true });
  }
}

function writeOperatorSeed(seed: OperatorSeed) {
  ensureOperatorSeedDir();
  fs.writeFileSync(getOperatorSeedPath(), `${JSON.stringify(seed, null, 2)}\n`, "utf-8");
  cachedOperator = seed;
  operatorLoadError = null;
}

function getOperatorState() {
  if (cachedOperator) {
    return { operator: cachedOperator, missing: false, malformed: false };
  }

  try {
    cachedOperator = loadOperatorSeed();
    operatorLoadError = null;
    return { operator: cachedOperator, missing: false, malformed: false };
  } catch (error) {
    operatorLoadError = error instanceof Error ? error : new Error(String(error));
    const missing = operatorLoadError.message.toLowerCase().includes("missing or unreadable");
    return { operator: null, missing, malformed: !missing };
  }
}

function getOperatorSeed() {
  const state = getOperatorState();
  if (!state.operator) {
    throw operatorLoadError ?? new Error("[AUTH] Operator seed file unavailable");
  }
  return state.operator;
}

function derivePasswordHash(password: string, salt: string) {
  return scryptSync(password, salt, 64).toString("hex");
}

function verifyPassword(password: string, operator: OperatorSeed) {
  const actual = Buffer.from(derivePasswordHash(password, operator.password_salt), "hex");
  const expected = Buffer.from(operator.password_hash, "hex");
  if (actual.length !== expected.length) {
    return false;
  }
  return timingSafeEqual(actual, expected);
}

export function verifyOperatorSeedPassword(password: string, operator: {
  password_hash: string;
  password_salt: string;
}) {
  return verifyPassword(password, {
    ...operator,
    username: "operator",
    hash_scheme: "scrypt",
    created_at: "",
    updated_at: "",
  });
}

function getRateLimitKey(req: Request, username: string) {
  return `${req.ip || "unknown"}:${username.toLowerCase()}`;
}

function getRateLimitState(key: string, now: number) {
  const current = rateLimitState.get(key);
  if (!current) {
    return { attempts: [], blockedUntil: 0 };
  }

  const attempts = current.attempts.filter((ts) => now - ts <= LOGIN_WINDOW_MS);
  const blockedUntil = current.blockedUntil > now ? current.blockedUntil : 0;
  return { attempts, blockedUntil };
}

function checkLoginRateLimit(req: Request, username: string): RateLimitResult {
  const now = Date.now();
  const key = getRateLimitKey(req, username);
  const current = getRateLimitState(key, now);
  rateLimitState.set(key, current);

  if (current.blockedUntil > now) {
    return { allowed: false, retryAfterMs: current.blockedUntil - now };
  }

  return { allowed: true, retryAfterMs: 0 };
}

function registerFailedLogin(req: Request, username: string) {
  const now = Date.now();
  const key = getRateLimitKey(req, username);
  const current = getRateLimitState(key, now);
  current.attempts.push(now);
  if (current.attempts.length >= LOGIN_MAX_ATTEMPTS) {
    current.blockedUntil = now + LOGIN_BLOCK_MS;
    current.attempts = [];
  }
  rateLimitState.set(key, current);
  return current.blockedUntil > now ? current.blockedUntil - now : 0;
}

function clearLoginRateLimit(req: Request, username: string) {
  rateLimitState.delete(getRateLimitKey(req, username));
}

function parseCookieHeader(cookieHeader: string | undefined, cookieName: string) {
  if (!cookieHeader) {
    return undefined;
  }

  for (const part of cookieHeader.split(";")) {
    const [name, ...valueParts] = part.trim().split("=");
    if (name === cookieName) {
      return decodeURIComponent(valueParts.join("="));
    }
  }

  return undefined;
}

function getPotentialSessionMarker(req: Request) {
  return parseCookieHeader(req.headers.cookie, SESSION_COOKIE_NAME);
}

function buildUnauthorizedDetails(req: Request, reason: "unauthorized_access" | "invalid_or_expired_session") {
  return {
    method: req.method,
    path: req.originalUrl || req.path,
    session_marker: getPotentialSessionMarker(req),
    reason,
  };
}

async function attachSessionWithMiddleware(req: Request, sessionMiddleware: RequestHandler) {
  await new Promise<void>((resolve, reject) => {
    sessionMiddleware(req, {} as Response, (error?: unknown) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

function getRequestOperator(req: Request) {
  return req.session?.operator;
}

export function initializeAuth(app: Express): AuthService {
  const startupOperatorState = getOperatorState();
  if (startupOperatorState.malformed) {
    throw operatorLoadError ?? new Error("[AUTH] Operator seed file is malformed");
  }

  const sessionStore = new MemoryStore({
    checkPeriod: 24 * 60 * 60 * 1000,
    stale: false,
  });

  if (isProduction()) {
    app.set("trust proxy", 1);
  }

  const sessionMiddleware = session({
    name: SESSION_COOKIE_NAME,
    secret: getSessionSecret(),
    resave: false,
    saveUninitialized: false,
    rolling: false,
    store: sessionStore,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: isProduction(),
    },
  });

  app.use(sessionMiddleware);

  app.post("/api/auth/login", expressJsonGuard, async (req, res) => {
    const username = typeof req.body?.username === "string" ? req.body.username.trim() : "";
    const password = typeof req.body?.password === "string" ? req.body.password : "";

    if (!username || !password) {
      await auditLogger.log({
        event_type: "login_failure",
        success: false,
        username: username || undefined,
        req,
        details: { reason: "missing_credentials" },
      });
      return res.status(400).json({ error: "Username and password are required" });
    }

    const operatorState = getOperatorState();
    if (operatorState.malformed) {
      await auditLogger.log({
        event_type: "login_failure",
        success: false,
        username: username || undefined,
        req,
        details: { reason: "operator_seed_malformed", error: operatorLoadError?.message },
      });
      return res.status(500).json({ error: "Operator configuration is malformed. Fix the seed file before signing in." });
    }

    if (operatorState.missing) {
      const bootstrapSeed = generateOperatorSeed(username, password);
      writeOperatorSeed(bootstrapSeed);

      req.session.regenerate(async (error) => {
        if (error) {
          await auditLogger.log({
            event_type: "operator_bootstrap_failure",
            success: false,
            username,
            req,
            details: { reason: "session_regenerate_failed", error: String(error) },
          });
          return res.status(500).json({ error: "Failed to establish session" });
        }

        req.session.operator = {
          username: bootstrapSeed.username,
          authenticatedAt: new Date().toISOString(),
        };

        await auditLogger.log({
          event_type: "operator_bootstrap_success",
          success: true,
          username: bootstrapSeed.username,
          req,
          details: { path: getOperatorSeedPath() },
        });

        return res.json(getSessionResponseFromOperator(req.session.operator));
      });

      return;
    }

    const operator = operatorState.operator!;

    const rateLimit = checkLoginRateLimit(req, username);
    if (!rateLimit.allowed) {
      await auditLogger.log({
        event_type: "login_rate_limited",
        success: false,
        username,
        req,
        details: { retry_after_ms: rateLimit.retryAfterMs },
      });
      res.setHeader("Retry-After", Math.ceil(rateLimit.retryAfterMs / 1000));
      return res.status(429).json({ error: "Too many login attempts. Try again later." });
    }

    if (operator.disabled) {
      await auditLogger.log({
        event_type: "login_failure",
        success: false,
        username,
        req,
        details: { reason: "operator_disabled" },
      });
      return res.status(403).json({ error: "Operator account disabled" });
    }

    if (username !== operator.username || !verifyPassword(password, operator)) {
      const retryAfterMs = registerFailedLogin(req, username);
      await auditLogger.log({
        event_type: "login_failure",
        success: false,
        username,
        req,
        details: {
          reason: username !== operator.username ? "invalid_username" : "invalid_password",
          retry_after_ms: retryAfterMs || undefined,
        },
      });
      return res.status(401).json({ error: "Invalid username or password" });
    }

    clearLoginRateLimit(req, username);

    req.session.regenerate(async (error) => {
      if (error) {
        await auditLogger.log({
          event_type: "login_failure",
          success: false,
          username,
          req,
          details: { reason: "session_regenerate_failed", error: String(error) },
        });
        return res.status(500).json({ error: "Failed to establish session" });
      }

      req.session.operator = {
        username: operator.username,
        authenticatedAt: new Date().toISOString(),
      };

      await auditLogger.log({
        event_type: "login_success",
        success: true,
        username: operator.username,
        req,
      });

      return res.json(getSessionResponseFromOperator(req.session.operator));
    });
  });

  app.post("/api/auth/logout", async (req, res) => {
    const current = req.session?.operator;

    req.session.destroy(async (error) => {
      res.clearCookie(SESSION_COOKIE_NAME);

      if (error) {
        await auditLogger.log({
          event_type: "logout_failure",
          success: false,
          username: current?.username,
          req,
          details: { error: String(error) },
        });
        return res.status(500).json({ error: "Failed to logout" });
      }

      await auditLogger.log({
        event_type: "logout",
        success: true,
        username: current?.username,
        req,
      });

      return res.json({ success: true, authenticated: false });
    });
  });

  app.get("/api/auth/session", (req, res) => {
    res.json(getSessionResponse(req));
  });

  app.get("/api/audit", requireAuthHandler, async (req, res) => {
    const limit = req.query.limit ? Math.max(1, Math.min(500, parseInt(String(req.query.limit), 10))) : 100;
    const offset = req.query.offset ? Math.max(0, parseInt(String(req.query.offset), 10)) : 0;

    try {
      const result = await auditLogger.list({ limit, offset });
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: "Failed to read audit log", details: String(error) });
    }
  });

  async function requireAuthHandler(req: Request, res: Response, next: () => void) {
    const operatorSession = getRequestOperator(req);
    if (operatorSession) {
      return next();
    }

    const hasSessionMarker = Boolean(getPotentialSessionMarker(req));
    await auditLogger.log({
      event_type: hasSessionMarker ? "invalid_or_expired_session" : "unauthorized_access",
      success: false,
      username: undefined,
      req,
      details: buildUnauthorizedDetails(
        req,
        hasSessionMarker ? "invalid_or_expired_session" : "unauthorized_access",
      ),
    });

    return res.status(401).json({ error: "Authentication required" });
  }

  function getSessionResponseFromOperator(operatorSession?: OperatorSession): AuthSessionResponse {
    if (!operatorSession) {
      return {
        authenticated: false,
        session_type: "session_cookie",
        setup_required: getOperatorState().missing,
      };
    }
    return {
      authenticated: true,
      username: operatorSession.username,
      session_type: "session_cookie",
    };
  }

  function getSessionResponse(req: Request) {
    return getSessionResponseFromOperator(getRequestOperator(req));
  }

  function auditProtectedAction(
    eventType: string,
    detailsFactory?: (req: Request, res: Response) => AuditDetailsInput | undefined,
  ): RequestHandler {
    return (req, res, next) => {
      res.on("finish", () => {
        const operatorSession = getRequestOperator(req);
        if (!operatorSession) {
          return;
        }

        if (res.statusCode >= 200 && res.statusCode < 500) {
          void auditLogger.log({
            event_type: eventType,
            success: res.statusCode < 400,
            username: operatorSession.username,
            req,
            details: detailsFactory?.(req, res),
          });
        }
      });

      next();
    };
  }

  return {
    sessionMiddleware,
    requireAuth: requireAuthHandler,
    attachSession: async (req: Request) => {
      await attachSessionWithMiddleware(req, sessionMiddleware);
    },
    getSessionResponse,
    auditProtectedAction,
    isPublicHealthSafe: () => true,
  };
}

function expressJsonGuard(req: Request, res: Response, next: () => void) {
  if (req.body && typeof req.body === "object") {
    next();
    return;
  }
  res.status(400).json({ error: "Invalid JSON body" });
}

export function generateOperatorSeed(username: string, password: string) {
  const password_salt = randomUUID();
  return {
    username,
    password_hash: derivePasswordHash(password, password_salt),
    password_salt,
    hash_scheme: "scrypt" as const,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function resetAuthStateForTests() {
  cachedOperator = null;
  operatorLoadError = null;
  rateLimitState.clear();
}
