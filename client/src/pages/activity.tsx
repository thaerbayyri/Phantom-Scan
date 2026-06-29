import { useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, ShieldCheck, ShieldAlert, ActivitySquare } from "lucide-react";
import { Link } from "wouter";
import type { AuditRecord } from "@shared/schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type AuditResponse = {
  total: number;
  records: AuditRecord[];
};

export default function ActivityPage() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadAudit = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/audit?limit=200", { credentials: "include" });
      if (!response.ok) {
        throw new Error("Failed to load audit log");
      }
      const data = (await response.json()) as AuditResponse;
      setRecords(data.records);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAudit();
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <div className="h-14 border-b bg-card flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <ArrowLeft className="h-4 w-4" />
              Dashboard
            </Button>
          </Link>
          <div className="h-6 w-px bg-border" />
          <ActivitySquare className="h-4 w-4 text-primary" />
          <h1 className="text-lg font-semibold tracking-tight">Operator Activity</h1>
          <Badge variant="secondary" className="text-[10px]">{total} events</Badge>
        </div>

        <Button variant="outline" size="sm" onClick={loadAudit} className="gap-1.5 text-xs" disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <main className="flex-1 overflow-auto p-4">
        <div className="mx-auto max-w-5xl space-y-3">
          {records.map((record, index) => (
            <Card key={`${record.ts}-${record.event_type}-${index}`} className="border-white/10 bg-card/70">
              <CardContent className="p-4 flex items-start gap-4">
                <div className={`mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl border ${
                  record.success
                    ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
                    : "border-amber-500/25 bg-amber-500/10 text-amber-400"
                }`}>
                  {record.success ? <ShieldCheck className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{record.event_type.replaceAll("_", " ")}</span>
                    <Badge variant={record.success ? "default" : "outline"} className="text-[10px]">
                      {record.success ? "SUCCESS" : "BLOCKED"}
                    </Badge>
                    {record.username ? <Badge variant="secondary" className="text-[10px]">{record.username}</Badge> : null}
                  </div>

                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>{new Date(record.ts).toLocaleString()}</span>
                    {record.route ? <span>{record.route}</span> : null}
                    {record.ip ? <span>{record.ip}</span> : null}
                  </div>

                  {record.details ? (
                    <pre className="mt-3 overflow-x-auto rounded-xl bg-background/70 p-3 text-xs text-muted-foreground">
                      {JSON.stringify(record.details, null, 2)}
                    </pre>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
