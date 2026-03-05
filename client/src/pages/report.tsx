import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    RefreshCw,
    FileText,
    Activity,
    Crosshair,
    Gauge,
    Clock,
    User,
    Cog,
    AlertTriangle,
    MapPin,
    Zap,
    TrendingUp,
} from "lucide-react";
import { Link } from "wouter";

// ─── Types ──────────────────────────────────────────────────────────

interface SessionEvent {
    time: number;
    elapsed: number;
    elapsedFormatted: string;
    description: string;
    distance?: number;
}

interface SessionReport {
    sessionId: string;
    startTime: number;
    endTime: number;
    durationS: number;
    totalFrames: number;
    isActive: boolean;
    targetClassification: string;
    classificationConfidence: number;
    classificationBreakdown: Record<string, number>;
    spatialMetrics: {
        minDistanceCm: number;
        maxDistanceCm: number;
        avgDistanceCm: number;
        boundingBox: {
            xMin: number;
            xMax: number;
            zMin: number;
            zMax: number;
        };
    };
    kinematicData: {
        avgSpeedMs: number;
        maxSpeedMs: number;
    };
    eventTimeline: SessionEvent[];
}

// ─── Helper components ──────────────────────────────────────────────

function MetricCard({
    icon: Icon,
    label,
    value,
    unit,
    color,
}: {
    icon: typeof Activity;
    label: string;
    value: string | number;
    unit?: string;
    color: string;
}) {
    return (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
            <div className={`p-2 rounded-lg ${color}`}>
                <Icon className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{label}</p>
                <p className="text-lg font-semibold font-mono">
                    {value}
                    {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
                </p>
            </div>
        </div>
    );
}

function ConfidenceBar({
    label,
    value,
    count,
    total,
    color,
}: {
    label: string;
    value: number;
    count: number;
    total: number;
    color: string;
}) {
    const pct = total > 0 ? (count / total) * 100 : 0;
    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono text-foreground">{pct.toFixed(1)}% ({count})</span>
            </div>
            <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

// ─── Main Report Page ───────────────────────────────────────────────

export default function ReportPage({ params }: { params?: { id?: string } }) {
    const sessionId = params?.id;
    const isHistorical = !!sessionId;

    const [report, setReport] = useState<SessionReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [autoRefresh, setAutoRefresh] = useState(!isHistorical);

    const fetchReport = useCallback(async () => {
        try {
            setLoading(true);
            const url = isHistorical ? `/api/sessions/${sessionId}` : "/api/report";
            const res = await fetch(url);
            if (!res.ok) throw new Error(res.status === 404 ? "Session not found" : "Failed to fetch report");
            const data = await res.json();
            setReport(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, [sessionId, isHistorical]);

    useEffect(() => {
        fetchReport();
    }, [fetchReport]);

    // Auto-refresh every 3 seconds when active (only for live reports)
    useEffect(() => {
        if (!autoRefresh || isHistorical) return;
        const interval = setInterval(fetchReport, 3000);
        return () => clearInterval(interval);
    }, [autoRefresh, fetchReport, isHistorical]);

    const formatDuration = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}m ${s}s`;
    };

    const classificationColor = (label: string) => {
        switch (label) {
            case "human": return "text-cyan-400";
            case "mechanical": return "text-amber-400";
            default: return "text-muted-foreground";
        }
    };

    const classificationIcon = (label: string) => {
        switch (label) {
            case "human": return User;
            case "mechanical": return Cog;
            default: return Activity;
        }
    };

    const ClassIcon = report ? classificationIcon(report.targetClassification) : Activity;

    return (
        <div className="flex flex-col min-h-screen bg-background">
            {/* Header */}
            <div className="h-14 border-b bg-card flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-3">
                    <Link href={isHistorical ? "/history" : "/"}>
                        <Button variant="ghost" size="sm" className="gap-1.5">
                            <ArrowLeft className="h-4 w-4" />
                            {isHistorical ? "History" : "Dashboard"}
                        </Button>
                    </Link>
                    <div className="h-6 w-px bg-border" />
                    <FileText className="h-4 w-4 text-primary" />
                    <h1 className="text-lg font-semibold tracking-tight">Session Report</h1>
                    {!isHistorical && report?.isActive && (
                        <Badge variant="default" className="gap-1 bg-green-600 animate-pulse text-[10px]">
                            LIVE
                        </Badge>
                    )}
                    {isHistorical && (
                        <Badge variant="secondary" className="text-[10px]">SAVED</Badge>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {!isHistorical && (
                        <Button
                            variant={autoRefresh ? "default" : "outline"}
                            size="sm"
                            onClick={() => setAutoRefresh(!autoRefresh)}
                            className="gap-1.5 text-xs"
                        >
                            <RefreshCw className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} style={autoRefresh ? { animationDuration: "3s" } : {}} />
                            {autoRefresh ? "Auto" : "Manual"}
                        </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={fetchReport} className="gap-1.5 text-xs">
                        <RefreshCw className="h-3.5 w-3.5" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Content */}
            <main className="flex-1 p-4 overflow-auto">
                {loading && !report ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="flex items-center gap-3 text-muted-foreground">
                            <RefreshCw className="h-5 w-5 animate-spin" />
                            <span>Loading report...</span>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="flex items-center gap-3 text-destructive">
                            <AlertTriangle className="h-5 w-5" />
                            <span>{error}</span>
                            <Button variant="outline" size="sm" onClick={fetchReport}>Retry</Button>
                        </div>
                    </div>
                ) : report && report.totalFrames === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 gap-4">
                        <FileText className="h-12 w-12 text-muted-foreground/30" />
                        <p className="text-muted-foreground">No session data yet. Start processing on the dashboard to begin collecting data.</p>
                        <Link href="/">
                            <Button variant="default" size="sm" className="gap-1.5">
                                <ArrowLeft className="h-4 w-4" />
                                Go to Dashboard
                            </Button>
                        </Link>
                    </div>
                ) : report ? (
                    <div className="max-w-5xl mx-auto space-y-4">
                        {/* Session Overview Banner */}
                        <Card className="overflow-hidden">
                            <div className="relative bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-6">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">Session Report</p>
                                        <h2 className="text-2xl font-bold tracking-tight mb-2">
                                            {report.sessionId}
                                        </h2>
                                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                            <span className="flex items-center gap-1">
                                                <Clock className="h-3.5 w-3.5" />
                                                {formatDuration(report.durationS)}
                                            </span>
                                            <span className="font-mono">{report.totalFrames.toLocaleString()} frames</span>
                                            {report.isActive && (
                                                <Badge variant="default" className="bg-green-600 text-[10px]">RECORDING</Badge>
                                            )}
                                        </div>
                                    </div>
                                    {/* Classification hero */}
                                    <div className="text-right">
                                        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl ${report.targetClassification === "human"
                                            ? "bg-cyan-500/10 border border-cyan-500/20"
                                            : report.targetClassification === "mechanical"
                                                ? "bg-amber-500/10 border border-amber-500/20"
                                                : "bg-muted border border-border"
                                            }`}>
                                            <ClassIcon className={`h-6 w-6 ${classificationColor(report.targetClassification)}`} />
                                            <div className="text-left">
                                                <p className={`text-lg font-bold uppercase ${classificationColor(report.targetClassification)}`}>
                                                    {report.targetClassification}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {(report.classificationConfidence * 100).toFixed(1)}% confidence
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </Card>

                        {/* Metric Cards Grid */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            <MetricCard
                                icon={Crosshair}
                                label="Avg Distance"
                                value={(report.spatialMetrics.avgDistanceCm / 100).toFixed(2)}
                                unit="m"
                                color="bg-blue-500/10 text-blue-400"
                            />
                            <MetricCard
                                icon={MapPin}
                                label="Min / Max Distance"
                                value={`${(report.spatialMetrics.minDistanceCm / 100).toFixed(1)} – ${(report.spatialMetrics.maxDistanceCm / 100).toFixed(1)}`}
                                unit="m"
                                color="bg-green-500/10 text-green-400"
                            />
                            <MetricCard
                                icon={Gauge}
                                label="Avg Speed"
                                value={report.kinematicData.avgSpeedMs.toFixed(3)}
                                unit="m/s"
                                color="bg-purple-500/10 text-purple-400"
                            />
                            <MetricCard
                                icon={Zap}
                                label="Max Speed"
                                value={report.kinematicData.maxSpeedMs.toFixed(3)}
                                unit="m/s"
                                color="bg-orange-500/10 text-orange-400"
                            />
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {/* Classification Breakdown */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-sm flex items-center gap-2">
                                        <User className="h-4 w-4 text-cyan-400" />
                                        Classification Breakdown
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    {Object.keys(report.classificationBreakdown).length > 0 ? (
                                        (() => {
                                            const total = Object.values(report.classificationBreakdown).reduce((s, v) => s + v, 0);
                                            return Object.entries(report.classificationBreakdown)
                                                .sort((a, b) => b[1] - a[1])
                                                .map(([label, count]) => (
                                                    <ConfidenceBar
                                                        key={label}
                                                        label={label.charAt(0).toUpperCase() + label.slice(1)}
                                                        value={count / total}
                                                        count={count}
                                                        total={total}
                                                        color={
                                                            label === "human"
                                                                ? "bg-gradient-to-r from-cyan-600 to-cyan-400"
                                                                : label === "mechanical"
                                                                    ? "bg-gradient-to-r from-amber-600 to-amber-400"
                                                                    : "bg-gradient-to-r from-gray-500 to-gray-400"
                                                        }
                                                    />
                                                ));
                                        })()
                                    ) : (
                                        <p className="text-sm text-muted-foreground italic">No classification data yet</p>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Spatial / Bounding Box */}
                            <Card>
                                <CardHeader className="pb-3">
                                    <CardTitle className="text-sm flex items-center gap-2">
                                        <MapPin className="h-4 w-4 text-green-400" />
                                        Spatial Analysis
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-4">
                                        {/* Distance gauge */}
                                        <div>
                                            <p className="text-xs text-muted-foreground mb-2">Distance Range</p>
                                            <div className="relative h-8 rounded-lg bg-muted/30 overflow-hidden">
                                                {/* Range bar */}
                                                {report.spatialMetrics.maxDistanceCm > 0 && (
                                                    <div
                                                        className="absolute top-0 h-full bg-gradient-to-r from-blue-600/40 to-blue-400/40 border border-blue-500/30 rounded-lg"
                                                        style={{
                                                            left: `${(report.spatialMetrics.minDistanceCm / Math.max(report.spatialMetrics.maxDistanceCm * 1.2, 100)) * 100}%`,
                                                            width: `${Math.max(5, ((report.spatialMetrics.maxDistanceCm - report.spatialMetrics.minDistanceCm) / Math.max(report.spatialMetrics.maxDistanceCm * 1.2, 100)) * 100)}%`,
                                                        }}
                                                    />
                                                )}
                                                {/* Average marker */}
                                                <div
                                                    className="absolute top-0 h-full w-0.5 bg-blue-400"
                                                    style={{
                                                        left: `${(report.spatialMetrics.avgDistanceCm / Math.max(report.spatialMetrics.maxDistanceCm * 1.2, 100)) * 100}%`,
                                                    }}
                                                />
                                                <div className="absolute inset-0 flex items-center justify-between px-3 text-[10px] font-mono text-muted-foreground">
                                                    <span>{(report.spatialMetrics.minDistanceCm / 100).toFixed(1)}m</span>
                                                    <span className="text-blue-400 font-bold">AVG {(report.spatialMetrics.avgDistanceCm / 100).toFixed(1)}m</span>
                                                    <span>{(report.spatialMetrics.maxDistanceCm / 100).toFixed(1)}m</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Bounding box */}
                                        <div>
                                            <p className="text-xs text-muted-foreground mb-2">Movement Bounding Box</p>
                                            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                                                <div className="p-2 rounded bg-muted/30 border border-border/50">
                                                    <span className="text-muted-foreground">X: </span>
                                                    <span>{report.spatialMetrics.boundingBox.xMin.toFixed(2)}</span>
                                                    <span className="text-muted-foreground"> → </span>
                                                    <span>{report.spatialMetrics.boundingBox.xMax.toFixed(2)}</span>
                                                    <span className="text-muted-foreground"> m</span>
                                                </div>
                                                <div className="p-2 rounded bg-muted/30 border border-border/50">
                                                    <span className="text-muted-foreground">Z: </span>
                                                    <span>{report.spatialMetrics.boundingBox.zMin.toFixed(2)}</span>
                                                    <span className="text-muted-foreground"> → </span>
                                                    <span>{report.spatialMetrics.boundingBox.zMax.toFixed(2)}</span>
                                                    <span className="text-muted-foreground"> m</span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Kinematic summary */}
                                        <div>
                                            <p className="text-xs text-muted-foreground mb-2">Velocity Profile</p>
                                            <div className="flex items-end gap-1 h-12">
                                                <div className="flex-1 flex flex-col items-center">
                                                    <div
                                                        className="w-full rounded-t bg-gradient-to-t from-purple-600 to-purple-400"
                                                        style={{ height: `${Math.min(100, (report.kinematicData.avgSpeedMs / Math.max(report.kinematicData.maxSpeedMs, 0.001)) * 100)}%` }}
                                                    />
                                                    <span className="text-[9px] text-muted-foreground mt-1">AVG</span>
                                                </div>
                                                <div className="flex-1 flex flex-col items-center">
                                                    <div
                                                        className="w-full rounded-t bg-gradient-to-t from-orange-600 to-orange-400"
                                                        style={{ height: "100%" }}
                                                    />
                                                    <span className="text-[9px] text-muted-foreground mt-1">MAX</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Event Timeline */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm flex items-center gap-2">
                                    <TrendingUp className="h-4 w-4 text-blue-400" />
                                    Event Timeline
                                    <Badge variant="secondary" className="ml-auto text-[10px]">
                                        {report.eventTimeline.length} events
                                    </Badge>
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {report.eventTimeline.length > 0 ? (
                                    <div className="relative">
                                        {/* Timeline line */}
                                        <div className="absolute left-[52px] top-0 bottom-0 w-px bg-border" />

                                        <div className="space-y-0">
                                            {report.eventTimeline.map((event, i) => {
                                                const isMotion = event.description.includes("moving");
                                                const isClassChange = event.description.includes("Classification");
                                                const isFall = event.description.includes("Fall");

                                                return (
                                                    <div key={i} className="flex items-start gap-3 py-2 group">
                                                        {/* Timestamp */}
                                                        <span className="text-xs font-mono text-muted-foreground w-10 text-right shrink-0 pt-0.5">
                                                            {event.elapsedFormatted}
                                                        </span>
                                                        {/* Dot */}
                                                        <div className={`relative z-10 mt-1 h-2.5 w-2.5 rounded-full border-2 shrink-0 ${isFall
                                                            ? "bg-red-500 border-red-400"
                                                            : isClassChange
                                                                ? "bg-amber-500 border-amber-400"
                                                                : isMotion
                                                                    ? "bg-blue-500 border-blue-400"
                                                                    : "bg-muted-foreground border-muted"
                                                            }`} />
                                                        {/* Description */}
                                                        <div className="flex-1 min-w-0">
                                                            <p className={`text-sm ${isFall ? "text-red-400 font-medium" : "text-foreground"}`}>
                                                                {event.description}
                                                            </p>
                                                            {event.distance && (
                                                                <p className="text-[10px] text-muted-foreground font-mono">
                                                                    Distance: {(event.distance / 100).toFixed(2)}m
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center py-8 text-muted-foreground">
                                        <Clock className="h-4 w-4 mr-2" />
                                        <span className="text-sm">No events recorded yet. Events are detected automatically during processing.</span>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                ) : null}
            </main>

            {/* Footer */}
            <footer className="h-8 border-t bg-card flex items-center justify-center px-4 shrink-0">
                <div className="text-xs text-muted-foreground">
                    Phantom Scan — Contextual Reporting Module
                </div>
            </footer>
        </div>
    );
}
