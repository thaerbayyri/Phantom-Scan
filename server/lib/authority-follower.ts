export class AuthorityFollower {
  private timer: NodeJS.Timeout | null = null;
  private readonly intervalMs = parseInt(process.env.PHANTOM_AUTHORITY_POLL_MS ?? "250", 10);

  start(): void {
    if (this.timer) {
      return;
    }
    console.warn("[AUTHORITY] Authority follower is disabled in ESP32/demo-only mode.");
    this.timer = setInterval(() => {
      // Keep the compatibility class inert so older imports do not restart the removed authority path.
    }, this.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
