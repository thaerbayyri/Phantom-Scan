import { useState } from "react";
import { Shield, LockKeyhole, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";

export default function LoginPage() {
  const { login, session } = useAuth();
  const [username, setUsername] = useState("thaer");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(username, password);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_38%),radial-gradient(circle_at_80%_20%,rgba(34,197,94,0.12),transparent_24%)]" />
      <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:32px_32px]" />

      <div className="relative z-10 flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-5xl grid gap-8 lg:grid-cols-[1.15fr_0.85fr] items-stretch">
          <div className="hidden lg:flex flex-col justify-between rounded-3xl border border-white/10 bg-card/70 backdrop-blur-xl p-8">
            <div className="space-y-6">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                <Shield className="h-6 w-6" />
              </div>
              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.35em] text-primary/80">Operator Access</p>
                <h1 className="text-4xl font-semibold tracking-tight">Phantom Scan Control Surface</h1>
                <p className="max-w-xl text-sm text-muted-foreground">
                  Authenticate as the designated operator to access live sensing, session history, reporting,
                  and runtime control paths.
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-background/50 p-4">
                <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Scope</p>
                <p className="mt-2 text-sm font-medium">Single operator only</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-background/50 p-4">
                <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Runtime</p>
                <p className="mt-2 text-sm font-medium">Session cookie auth</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-background/50 p-4">
                <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Audit</p>
                <p className="mt-2 text-sm font-medium">Access attempts recorded</p>
              </div>
            </div>
          </div>

          <Card className="border-white/10 bg-card/80 backdrop-blur-xl shadow-2xl">
            <CardContent className="p-8 sm:p-10">
              <div className="mb-8 space-y-2">
                <p className="text-xs uppercase tracking-[0.35em] text-primary/80">Login</p>
                <h2 className="text-2xl font-semibold tracking-tight">Operator sign in</h2>
                <p className="text-sm text-muted-foreground">
                  {session.setup_required
                    ? "No operator file exists yet. Enter the first operator username and password to initialize this dashboard."
                    : "Use the operator username and password. Public signup is disabled."}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    className="h-11"
                  />
                </div>

                {error ? (
                  <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                ) : null}

                <Button type="submit" className="h-11 w-full gap-2" disabled={submitting}>
                  <LockKeyhole className="h-4 w-4" />
                  {submitting ? "Signing in..." : "Sign in"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
