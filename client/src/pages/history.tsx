import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    Search,
    RefreshCw,
    Trash2,
    FileText,
    Clock,
    Activity,
    User,
    Cog,
    Database,
    ChevronRight,
} from "lucide-react";
import { Link } from "wouter";

interface SessionSummary {
    id: string;
    name?: string;
    startTime: number;
    endTime: number;
    durationS: number;
    totalFrames: number;
    targetClassification: string;
    classificationConfidence: number;
    avgDistanceCm: number;
    avgSpeedMs: number;
    dataSource: string;
}

export default function HistoryPage() {
    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [classFilter, setClassFilter] = useState("");
    const [deleting, setDeleting] = useState<string | null>(null);

    const fetchSessions = useCallback(async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();
            if (search) params.set("search", search);
            if (classFilter) params.set("classification", classFilter);
            const res = await fetch(`/api/sessions?${params}`);
            if (!res.ok) throw new Error("Failed to fetch sessions");
            const data = await res.json();
            setSessions(data.sessions);
            setTotal(data.total);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [search, classFilter]);

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    const handleDelete = async (id: string) => {
        if (!confirm("Delete this session permanently?")) return;
        setDeleting(id);
        try {
            await fetch(`/api/sessions/${id}`, { method: "DELETE" });
            fetchSessions();
        } catch (err) {
            console.error(err);
        } finally {
            setDeleting(null);
        }
    };

    const formatDate = (ts: number) => {
        return new Date(ts).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const formatDuration = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
    };

    const classIcon = (label: string) =>
        label === "human" ? User : label === "mechanical" ? Cog : Activity;

    const classColor = (label: string) => {
        switch (label) {
            case "human": return "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
            case "mechanical": return "bg-amber-500/10 text-amber-400 border-amber-500/20";
            default: return "bg-muted text-muted-foreground border-border";
        }
    };

    return (
        <div className="flex flex-col min-h-screen bg-background">
            {/* Header */}
            <div className="h-14 border-b bg-card flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-3">
                    <Link href="/">
                        <Button variant="ghost" size="sm" className="gap-1.5">
                            <ArrowLeft className="h-4 w-4" />
                            Dashboard
                        </Button>
                    </Link>
                    <div className="h-6 w-px bg-border" />
                    <Database className="h-4 w-4 text-primary" />
                    <h1 className="text-lg font-semibold tracking-tight">Session History</h1>
                    <Badge variant="secondary" className="text-[10px]">{total} sessions</Badge>
                </div>
                <Button variant="outline" size="sm" onClick={fetchSessions} className="gap-1.5 text-xs">
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                </Button>
            </div>

            {/* Search & Filters */}
            <div className="border-b bg-card/50 px-4 py-3 flex items-center gap-3">
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Search sessions by ID, date, or source..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full h-9 pl-9 pr-3 rounded-lg bg-muted/50 border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all"
                    />
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="text-xs text-muted-foreground">Filter:</span>
                    {["", "human", "mechanical"].map((cls) => (
                        <Button
                            key={cls || "all"}
                            variant={classFilter === cls ? "default" : "outline"}
                            size="sm"
                            onClick={() => setClassFilter(cls)}
                            className="text-xs h-7 px-2.5"
                        >
                            {cls || "All"}
                        </Button>
                    ))}
                </div>
            </div>

            {/* Session List */}
            <main className="flex-1 p-4 overflow-auto">
                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 gap-4">
                        <Database className="h-12 w-12 text-muted-foreground/20" />
                        <p className="text-muted-foreground text-sm">
                            {search || classFilter
                                ? "No sessions match your search."
                                : "No sessions recorded yet. Start and stop processing to create sessions."}
                        </p>
                        {(search || classFilter) && (
                            <Button variant="outline" size="sm" onClick={() => { setSearch(""); setClassFilter(""); }}>
                                Clear filters
                            </Button>
                        )}
                    </div>
                ) : (
                    <div className="max-w-5xl mx-auto space-y-2">
                        {sessions.map((session) => {
                            const ClassIcon = classIcon(session.targetClassification);
                            return (
                                <Card
                                    key={session.id}
                                    className="group hover:border-primary/30 transition-colors cursor-pointer"
                                    onClick={() => window.location.href = `/report/${session.id}`}
                                >
                                    <CardContent className="p-4">
                                        <div className="flex items-center gap-4">
                                            {/* Classification icon */}
                                            <div className={`p-2.5 rounded-xl border ${classColor(session.targetClassification)}`}>
                                                <ClassIcon className="h-5 w-5" />
                                            </div>

                                            {/* Main info */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex flex-col mb-1">
                                                    <div className="flex items-center gap-2 mb-0.5">
                                                        <span className="text-sm font-semibold text-foreground truncate">
                                                            {session.name ? session.name : session.id}
                                                        </span>
                                                        <Badge variant="outline" className={`text-[10px] ${classColor(session.targetClassification)} border`}>
                                                            {session.targetClassification.toUpperCase()}
                                                        </Badge>
                                                    </div>
                                                    {session.name && (
                                                        <span className="text-xs text-muted-foreground font-mono truncate">
                                                            {session.id}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                                    <span className="flex items-center gap-1">
                                                        <Clock className="h-3 w-3" />
                                                        {formatDate(session.startTime)}
                                                    </span>
                                                    <span>{formatDuration(session.durationS)}</span>
                                                    <span className="font-mono">{session.totalFrames.toLocaleString()} frames</span>
                                                    <span className="capitalize">{session.dataSource}</span>
                                                </div>
                                            </div>

                                            {/* Metrics */}
                                            <div className="hidden md:flex items-center gap-6 text-xs">
                                                <div className="text-right">
                                                    <p className="text-muted-foreground">Distance</p>
                                                    <p className="font-mono font-semibold">{(session.avgDistanceCm / 100).toFixed(1)}m</p>
                                                </div>
                                                <div className="text-right">
                                                    <p className="text-muted-foreground">Confidence</p>
                                                    <p className="font-mono font-semibold">{(session.classificationConfidence * 100).toFixed(0)}%</p>
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex items-center gap-1.5">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDelete(session.id);
                                                    }}
                                                    disabled={deleting === session.id}
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </Button>
                                                <ChevronRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                )}
            </main>

            {/* Footer */}
            <footer className="h-8 border-t bg-card flex items-center justify-center px-4 shrink-0">
                <div className="text-xs text-muted-foreground">
                    Phantom Scan — Session History
                </div>
            </footer>
        </div>
    );
}
