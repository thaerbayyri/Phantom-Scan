import type { Request } from "express";
import fs from "fs";
import path from "path";

const ROTATED_PREFIX = "audit-";
const MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024;
const MAX_ROTATED_FILES = 10;

export type AuditDetailsInput = Record<string, unknown> | undefined;

export type AuditRecord = {
  ts: string;
  event_type: string;
  username?: string;
  success: boolean;
  ip?: string;
  user_agent?: string;
  route?: string;
  session_id?: string;
  details?: AuditDetailsInput;
};

type RequestLike = Partial<Request> & {
  headers?: Record<string, string | string[] | undefined>;
  method?: string;
  url?: string;
  originalUrl?: string;
  path?: string;
  ip?: string;
  sessionID?: string;
  get?: ((name: string) => string | undefined) | undefined;
};

function ensureAuditDir(dir: string) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getCurrentLogPath(dir: string) {
  return path.join(dir, "audit-current.jsonl");
}

function getRotatedFiles(dir: string) {
  ensureAuditDir(dir);
  return fs
    .readdirSync(dir)
    .filter((file) => file !== "audit-current.jsonl" && file.startsWith(ROTATED_PREFIX) && file.endsWith(".jsonl"))
    .sort()
    .reverse();
}

function rotateIfNeeded(dir: string) {
  ensureAuditDir(dir);
  const currentLog = getCurrentLogPath(dir);

  if (!fs.existsSync(currentLog)) {
    return;
  }

  const { size } = fs.statSync(currentLog);
  if (size < MAX_LOG_SIZE_BYTES) {
    return;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const rotatedPath = path.join(dir, `${ROTATED_PREFIX}${stamp}.jsonl`);
  fs.renameSync(currentLog, rotatedPath);

  const oldFiles = getRotatedFiles(dir);
  for (const file of oldFiles.slice(MAX_ROTATED_FILES)) {
    fs.unlinkSync(path.join(dir, file));
  }
}

function safeParseLine(line: string): AuditRecord | null {
  if (!line.trim()) {
    return null;
  }

  try {
    return JSON.parse(line) as AuditRecord;
  } catch {
    return null;
  }
}

export class AuditLogger {
  constructor(
    private readonly dir = process.env.PHANTOM_AUDIT_DIR || path.resolve("data", "audit"),
  ) {}

  async log(input: {
    event_type: string;
    success: boolean;
    username?: string;
    req?: RequestLike;
    details?: AuditDetailsInput;
  }) {
    try {
      rotateIfNeeded(this.dir);
      ensureAuditDir(this.dir);
      const currentLog = getCurrentLogPath(this.dir);

      const record: AuditRecord = {
        ts: new Date().toISOString(),
        event_type: input.event_type,
        username: input.username,
        success: input.success,
        ip: input.req?.ip,
        user_agent: this.getUserAgent(input.req),
        route: this.getRoute(input.req),
        session_id: input.req?.sessionID,
        details: input.details,
      };

      fs.appendFileSync(currentLog, `${JSON.stringify(record)}\n`, "utf-8");
    } catch (error) {
      console.error("[AUDIT] Failed to append audit record:", error);
    }
  }

  async list({ limit, offset }: { limit: number; offset: number }) {
    ensureAuditDir(this.dir);

    const files = [
      getCurrentLogPath(this.dir),
      ...getRotatedFiles(this.dir).map((file) => path.join(this.dir, file)),
    ];
    const records: AuditRecord[] = [];

    for (const file of files) {
      if (!fs.existsSync(file)) {
        continue;
      }

      const contents = fs.readFileSync(file, "utf-8");
      const parsed = contents
        .split(/\r?\n/)
        .map(safeParseLine)
        .filter((record): record is AuditRecord => Boolean(record));

      records.push(...parsed.reverse());
    }

    return {
      total: records.length,
      records: records.slice(offset, offset + limit),
    };
  }

  private getUserAgent(req?: RequestLike) {
    if (!req) {
      return undefined;
    }

    if (typeof req.get === "function") {
      return req.get("user-agent");
    }

    const header = req.headers?.["user-agent"];
    return Array.isArray(header) ? header[0] : header;
  }

  private getRoute(req?: RequestLike) {
    if (!req) {
      return undefined;
    }

    const pathValue = req.originalUrl || req.path || req.url;
    if (!pathValue) {
      return undefined;
    }

    return req.method ? `${req.method} ${pathValue}` : pathValue;
  }
}

export const auditLogger = new AuditLogger();
