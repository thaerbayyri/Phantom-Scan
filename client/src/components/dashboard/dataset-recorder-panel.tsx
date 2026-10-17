import { useState } from "react";
import type { DatasetStatus } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Database } from "lucide-react";

const LABELS = [
    { value: "empty", text: "Empty room" },
    { value: "empty_fan", text: "Empty + fan/HVAC" },
    { value: "still", text: "1 person, still" },
    { value: "walking", text: "1 person, walking" },
    { value: "active", text: "1 person, active" },
    { value: "two_people", text: "2 people" },
    { value: "three_people", text: "3 people" },
] as const;

const COUNTDOWN_S = 10;
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

interface DatasetRecorderPanelProps {
    status: DatasetStatus | null;
    onStart: (request: { roomId: string; subjectId: string; label: string }) => void;
    onStop: () => void;
}

/**
 * Operator control for labelled training-data capture (docs/DATASET_PROTOCOL.md).
 * Writes the real per-node amplitude vectors to data/datasets/ on the server;
 * a countdown gives the operator time to walk into position before frames
 * are labelled. Not an upstream hardware control (F2): it only records what
 * the server already receives.
 */
export function DatasetRecorderPanel({ status, onStart, onStop }: DatasetRecorderPanelProps) {
    const [roomId, setRoomId] = useState("room1");
    const [subjectId, setSubjectId] = useState("s1");
    const [label, setLabel] = useState<string>("empty");
    const [countdown, setCountdown] = useState<number | null>(null);

    const recording = status?.recording === true;
    const valid = ID_PATTERN.test(roomId) && ID_PATTERN.test(subjectId);

    const begin = () => {
        let remaining = COUNTDOWN_S;
        setCountdown(remaining);
        const timer = setInterval(() => {
            remaining -= 1;
            if (remaining <= 0) {
                clearInterval(timer);
                setCountdown(null);
                onStart({ roomId, subjectId, label });
            } else {
                setCountdown(remaining);
            }
        }, 1000);
    };

    return (
        <Card className="min-w-0 border-dashed border-cyan-400/30">
            <CardHeader className="flex flex-row items-center gap-2 px-5 pb-3 pt-5">
                <Database className="h-4 w-4 text-cyan-400" />
                <CardTitle className="min-w-0 text-base">Training Data Capture</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 px-5 pb-5 text-xs">
                <div className="grid grid-cols-2 gap-2">
                    <label className="space-y-1">
                        <span className="text-muted-foreground">Room ID</span>
                        <input
                            className="w-full rounded border border-white/10 bg-background px-2 py-1 font-mono"
                            value={roomId}
                            onChange={(e) => setRoomId(e.target.value)}
                            disabled={recording || countdown !== null}
                            data-testid="input-dataset-room"
                        />
                    </label>
                    <label className="space-y-1">
                        <span className="text-muted-foreground">Subject ID</span>
                        <input
                            className="w-full rounded border border-white/10 bg-background px-2 py-1 font-mono"
                            value={subjectId}
                            onChange={(e) => setSubjectId(e.target.value)}
                            disabled={recording || countdown !== null}
                            data-testid="input-dataset-subject"
                        />
                    </label>
                </div>
                <label className="block space-y-1">
                    <span className="text-muted-foreground">Label (ground truth for the whole recording)</span>
                    <select
                        className="w-full rounded border border-white/10 bg-background px-2 py-1"
                        value={label}
                        onChange={(e) => setLabel(e.target.value)}
                        disabled={recording || countdown !== null}
                        data-testid="select-dataset-label"
                    >
                        {LABELS.map((l) => (
                            <option key={l.value} value={l.value}>
                                {l.text}
                            </option>
                        ))}
                    </select>
                </label>
                {!valid && (
                    <div className="text-amber-300">IDs: 1-64 letters, digits, '_' or '-'.</div>
                )}
                {recording ? (
                    <div className="space-y-2">
                        <div className="font-mono text-cyan-300" data-testid="text-dataset-progress">
                            REC {status?.label} · {status?.frames ?? 0} frames
                            {status && status.skipped > 0 ? ` (${status.skipped} skipped)` : ""}
                        </div>
                        <div className="font-mono text-muted-foreground">
                            per node:{" "}
                            {Object.entries(status?.perNode ?? {})
                                .map(([id, n]) => `N${id}=${n}`)
                                .join(" ") || "none yet"}
                        </div>
                        <Button size="sm" variant="outline" onClick={onStop} data-testid="btn-dataset-stop">
                            Stop recording
                        </Button>
                    </div>
                ) : (
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={begin}
                        disabled={!valid || countdown !== null}
                        data-testid="btn-dataset-start"
                    >
                        {countdown !== null ? `Starting in ${countdown}s — take position` : "Start recording"}
                    </Button>
                )}
                {!recording && status && status.frames > 0 && (
                    <div className="text-muted-foreground">
                        Last: {status.frames} frames saved ({status.files.length} file{status.files.length === 1 ? "" : "s"}).
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
