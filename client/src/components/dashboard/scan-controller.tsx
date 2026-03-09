import { useState } from "react";
import { Play, Square, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";

interface ScanControllerProps {
    isProcessing: boolean;
    onStart: (caseName: string) => void;
    onStop: () => void;
    isRecording?: boolean;
}

export function ScanController({
    isProcessing,
    onStart,
    onStop,
    isRecording = false,
}: ScanControllerProps) {
    const [open, setOpen] = useState(false);
    const [caseName, setCaseName] = useState("");

    const handleStart = () => {
        if (!caseName.trim()) return;
        onStart(caseName.trim());
        setOpen(false);
        setCaseName(""); // reset for next time
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            handleStart();
        }
    };

    return (
        <>
            {isProcessing ? (
                <Button
                    variant="destructive"
                    size="sm"
                    onClick={onStop}
                    className="gap-1.5"
                    data-testid="btn-stop-processing"
                >
                    <Square className="h-3 w-3" />
                    End Scan / Close Case
                </Button>
            ) : (
                <Dialog open={open} onOpenChange={setOpen}>
                    <DialogTrigger asChild>
                        <Button
                            variant="default"
                            size="sm"
                            className="gap-1.5 bg-primary hover:bg-primary/90"
                            data-testid="btn-start-scan"
                        >
                            <Play className="h-3 w-3" />
                            Start Scan
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[425px]">
                        <DialogHeader>
                            <DialogTitle>Initialize New Case</DialogTitle>
                            <DialogDescription>
                                Enter a Case Name or Session ID to begin scanning and recording.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="flex flex-col gap-2">
                                <Input
                                    id="caseName"
                                    placeholder="e.g. Investigation_Alpha_01"
                                    value={caseName}
                                    onChange={(e) => setCaseName(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    className="col-span-3"
                                    autoFocus
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setOpen(false)}>
                                Cancel
                            </Button>
                            <Button onClick={handleStart} disabled={!caseName.trim()}>
                                Start Scan
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
        </>
    );
}
