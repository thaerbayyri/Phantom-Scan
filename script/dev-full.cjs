const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const isWindows = process.platform === "win32";
const venvPython = path.join(root, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const fallbackPython = isWindows
  ? "C:\\Users\\thaer\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
  : "python3";
const python = process.env.PHANTOM_PYTHON || (fs.existsSync(venvPython) ? venvPython : fallbackPython);
const authorityHost = process.env.PHANTOM_AUTHORITY_HOST || "127.0.0.1";
const authorityPort = process.env.PHANTOM_AUTHORITY_PORT || "8789";
const authorityUrl = process.env.PHANTOM_AUTHORITY_URL || `http://${authorityHost}:${authorityPort}`;
const dashboardHost = process.env.HOST || "0.0.0.0";
const preferredDashboardPort = Number.parseInt(process.env.PORT || "5000", 10);

const children = [];
let shuttingDown = false;

function start(command, args, env = {}) {
  const child = spawn(command, args, {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: "inherit",
    windowsHide: true,
  });
  children.push(child);
  child.on("exit", (code, signal) => {
    if (!shuttingDown && code !== 0) {
      console.error(`[dev-full] ${command} exited with code=${code} signal=${signal}`);
      shutdown(code || 1);
    }
  });
  return child;
}

function waitForAuthority(deadlineMs = 15000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      const req = http.get(`${authorityUrl}/api/status`, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
          return;
        }
        retry();
      });
      req.on("error", retry);
      req.setTimeout(1000, () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - startedAt > deadlineMs) {
        reject(new Error(`Python authority did not become ready at ${authorityUrl}`));
        return;
      }
      setTimeout(poll, 250);
    };
    poll();
  });
}

function canListen(port, host = dashboardHost) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

async function findDashboardPort() {
  for (let port = preferredDashboardPort; port < preferredDashboardPort + 20; port += 1) {
    if (await canListen(port)) {
      return port;
    }
  }
  throw new Error(`No available dashboard port from ${preferredDashboardPort} to ${preferredDashboardPort + 19}`);
}

function shutdown(code = 0) {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const child of children.reverse()) {
    if (!child.killed) {
      child.kill(isWindows ? undefined : "SIGTERM");
    }
  }
  setTimeout(() => process.exit(code), 250);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

(async () => {
  // Architecture note: the dashboard server (server/index.ts) owns UDP :5005
  // ingest directly (server/lib/udp-server.ts -> SignalProcessingServer) and
  // forwards accepted raw frames to the optional AI sidecar on :5006. The old
  // Python authority (`phantom.runtime live`) also bound :5005, which collided
  // with the dashboard's own bind — so it is no longer started here. Set
  // PHANTOM_USE_AUTHORITY=1 only if you intentionally want the Python authority
  // to own :5005 instead (in which case do not also run the dashboard ingest).
  if (process.env.PHANTOM_USE_AUTHORITY === "1") {
    console.log("[dev-full] PHANTOM_USE_AUTHORITY=1 -> starting Python authority on UDP 5005 and HTTP 8789");
    start(python, [
      "-m",
      "phantom.runtime",
      "live",
      "--host",
      "0.0.0.0",
      "--port",
      process.env.PHANTOM_UDP_PORT || "5005",
      "--api-host",
      authorityHost,
      "--api-port",
      authorityPort,
      "--forward-ai-host",
      process.env.PHANTOM_FORWARD_AI_HOST || "127.0.0.1",
      "--forward-ai-port",
      process.env.PHANTOM_FORWARD_AI_PORT || "5006",
      "--no-synthetic",
    ]);
    await waitForAuthority();
    console.log(`[dev-full] Python authority ready at ${authorityUrl}`);
  }

  const dashboardPort = await findDashboardPort();
  if (dashboardPort !== preferredDashboardPort) {
    console.warn(`[dev-full] dashboard port ${preferredDashboardPort} is busy; using ${dashboardPort}`);
  }
  console.log(`[dev-full] starting dashboard on port ${dashboardPort} (owns UDP :5005 ESP32 ingest)`);

  start(
    process.execPath,
    [path.join(root, "node_modules", "tsx", "dist", "cli.mjs"), "server/index.ts"],
    {
      NODE_ENV: "development",
      PORT: String(dashboardPort),
      PHANTOM_AUTHORITY_URL: authorityUrl,
    },
  );
})().catch((error) => {
  console.error(`[dev-full] ${error instanceof Error ? error.message : String(error)}`);
  shutdown(1);
});
