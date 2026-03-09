import { spawn, ChildProcess } from "child_process";
import os from "os";
import { type Response } from "express";

export function handleSecureTerminalStream(req: any, res: Response) {
    const { task } = req.query;

    // Strict Allowlist
    if (task !== "START_DIAGNOSTIC") {
        return res.status(400).json({ error: "Invalid or unauthorized task." });
    }

    // Set up Server-Sent Events (SSE) headers for real-time streaming
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");

    const isWindows = os.platform() === "win32";

    let cmd = "ping";
    let args: string[] = [];

    if (isWindows) {
        // OS-Aware Command Routing: Route through WSL on Windows
        // Using simple ping as a continuous diagnostic stream placeholder
        cmd = "wsl";
        args = ["-d", "Ubuntu", "--", "ping", "localhost", "-c", "20"];
    } else {
        // Native Linux continuous diagnostic stream
        cmd = "ping";
        args = ["localhost", "-c", "20"];
    }

    // Principle of Least Privilege: NO shell execution
    const child: ChildProcess = spawn(cmd, args, { shell: false });

    child.stdout?.on("data", (data) => {
        const lines = data.toString().split("\n");
        for (const line of lines) {
            if (line.trim()) {
                res.write(`data: ${JSON.stringify({ type: "stdout", msg: line })}\n\n`);
            }
        }
    });

    child.stderr?.on("data", (data) => {
        const lines = data.toString().split("\n");
        for (const line of lines) {
            if (line.trim()) {
                res.write(`data: ${JSON.stringify({ type: "stderr", msg: line })}\n\n`);
            }
        }
    });

    child.on("error", (error: any) => {
        if (error.code === "ENOENT") {
            res.write(
                `data: ${JSON.stringify({
                    type: "error",
                    msg: "Error: WSL environment not detected. Please see docs/wsl_usb_setup.md.",
                })}\n\n`
            );
        } else {
            res.write(`data: ${JSON.stringify({ type: "error", msg: error.message })}\n\n`);
        }
    });

    child.on("close", (code) => {
        res.write(`data: ${JSON.stringify({ type: "close", msg: `Stream ended with code ${code}` })}\n\n`);
        res.end();
    });

    // Ensure the subprocess is killed if the client disconnects
    req.on("close", () => {
        if (child && !child.killed) {
            child.kill();
        }
    });
}
