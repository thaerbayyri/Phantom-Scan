import { useState, useRef, useEffect } from "react";
import { TerminalSquare, Play, Square } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function VirtualTerminal() {
    const [output, setOutput] = useState<string>("System Terminal Ready...\nWaiting for connection.");
    const [isStreaming, setIsStreaming] = useState(false);
    const eventSourceRef = useRef<EventSource | null>(null);
    const endOfStreamRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (endOfStreamRef.current) {
            endOfStreamRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [output]);

    useEffect(() => {
        // Cleanup on unmount
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    const startStream = () => {
        if (isStreaming) return;
        setIsStreaming(true);
        setOutput("Initializing WSL diagnostic connection...\n");

        const eventSource = new EventSource("/api/v1/diagnostic/stream?task=START_DIAGNOSTIC");
        eventSourceRef.current = eventSource;

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "stdout" || data.type === "stderr") {
                setOutput((prev) => prev + data.msg + "\n");
            } else if (data.type === "error") {
                setOutput((prev) => prev + "\n[ERROR] " + data.msg + "\n");
                eventSource.close();
                setIsStreaming(false);
            } else if (data.type === "close") {
                setOutput((prev) => prev + "\n" + data.msg + "\n");
                eventSource.close();
                setIsStreaming(false);
            }
        };

        eventSource.onerror = (err) => {
            setOutput((prev) => prev + "\n[Stream Connection Error - EventSource Failed]\n");
            eventSource.close();
            setIsStreaming(false);
        };
    };

    const stopStream = () => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setIsStreaming(false);
        setOutput((prev) => prev + "\n[Stream manually terminated]\n");
    };

    return (
        <Card className="bg-sidebar border-none shadow-none h-[500px] flex flex-col">
            <CardHeader className="pb-3 px-4 pt-4 shrink-0">
                <div className="flex items-center gap-2">
                    <TerminalSquare className="h-5 w-5 text-emerald-500" />
                    <CardTitle className="text-lg font-medium">Diagnostic Virtual Terminal</CardTitle>
                </div>
                <CardDescription className="text-xs">
                    Securely stream continuous hardware diagnostic telemetry via WSL standard output.
                </CardDescription>
            </CardHeader>

            <CardContent className="px-4 pb-4 space-y-4 flex-1 flex flex-col min-h-0">
                <div className="flex gap-2 shrink-0">
                    {!isStreaming ? (
                        <Button size="sm" onClick={startStream} className="w-56 text-xs gap-2">
                            <Play className="h-3 w-3" /> Start Diagnostic Stream
                        </Button>
                    ) : (
                        <Button size="sm" variant="destructive" onClick={stopStream} className="w-56 text-xs gap-2">
                            <Square className="h-3 w-3" /> Stop Stream
                        </Button>
                    )}
                </div>

                <div className="rounded-md bg-[#1e1e1e] border border-white/20 p-3 flex-1 overflow-y-auto w-full relative">
                    <pre className="text-[12px] font-mono text-green-400 whitespace-pre-wrap leading-relaxed font-medium text-left">
                        {output}
                        <div ref={endOfStreamRef} />
                    </pre>
                </div>
            </CardContent>
        </Card>
    );
}
