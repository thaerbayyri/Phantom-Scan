import type { IncomingMessage } from "http";
import type { Request } from "express";
import type { AuthService } from "./service";
import { auditLogger } from "../audit/logger";

export async function authenticateWebSocketRequest(
  request: IncomingMessage,
  auth: AuthService,
) {
  const req = request as Request;
  await auth.attachSession(req);
  const session = auth.getSessionResponse(req);
  if (!session.authenticated || !session.username) {
    const hasSessionCookie = Boolean(req.headers.cookie?.includes("phantom.sid="));
    await auditLogger.log({
      event_type: hasSessionCookie ? "invalid_or_expired_session" : "unauthorized_access",
      success: false,
      req,
      details: {
        protocol: "websocket",
        path: req.url,
      },
    });
    return null;
  }

  return {
    username: session.username,
  };
}
