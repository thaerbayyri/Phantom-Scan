import { useState, useEffect } from "react";
import { Terminal, Activity, RefreshCw, FileText, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

type TaskName = "START_MONITOR" | "STOP_MONITOR" | "RESTART_BACKEND" | "VIEW_LOGS" | "CHECK_WIFI";

interface TaskButton {
    id: TaskName;
    label: string;
    icon: JSX.Element;
    variant: "default" | "destructive" | "outline" | "secondary";
}

const TASKS: TaskButton[] = [
    { id: "START_MONITOR", label: "Start Monitor Mode", icon: <Wifi className="w-4 h-4 mr-2" />, variant: "default" },
    { id: "STOP_MONITOR", label: "Stop Monitor Mode", icon: <Wifi className="w-4 h-4 mr-2" />, variant: "destructive" },
    { id: "RESTART_BACKEND", label: "Restart Node Server", icon: <RefreshCw className="w-4 h-4 mr-2" />, variant: "secondary" },
    { id: "VIEW_LOGS", label: "Fetch Recent Logs", icon: <FileText className="w-4 h-4 mr-2" />, variant: "outline" },
    { id: "CHECK_WIFI", label: "Check Interfaces", icon: <Activity className="w-4 h-4 mr-2" />, variant: "outline" },
];

export function SystemControlPanel() {
    const [output, setOutput] = useState<string>("System Terminal Ready...\nWaiting for task execution.");
    const [isExecuting, setIsExecuting] = useState(false);
    const [interfaceName, setInterfaceName] = useState("wlan0");
    const [availableInterfaces, setAvailableInterfaces] = useState<string[]>(["wlan0"]);
    const { toast } = useToast();

    useEffect(() => {
        fetch("/api/v1/system/interfaces")
            .then((res) => res.json())
            .then((data) => {
                if (data.interfaces && Array.isArray(data.interfaces)) {
                    // Filter to only wireless-looking or typical name patterns
                    const wifiIfaces = data.interfaces.filter((name: string) => {
                        const n = name.toLowerCase();
                        return n.includes("wlan") ||
                            n.includes("wi-fi") ||
                            n.includes("wireless") ||
                            n.startsWith("wl") ||
                            n === "wifi";
                    });

                    // Fallback to all if none match our heuristics
                    const options = wifiIfaces.length > 0 ? wifiIfaces : data.interfaces;

                    setAvailableInterfaces(options);
                    // Auto-select first if wlan0 isn't available
                    if (!options.includes("wlan0") && options.length > 0) {
                        setInterfaceName(options[0]);
                    } else if (options.includes("wlan0")) {
                        setInterfaceName("wlan0");
                    }
                }
            })
            .catch((err) => console.error("Failed to load interfaces:", err));
    }, []);

    const handleExecute = async (task: TaskName) => {
        setIsExecuting(true);
        setOutput(`Executing: ${task} on interface ${interfaceName}...\n`);

        try {
            const res = await fetch("/api/v1/system/execute-task", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task, interfaceName }),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error || "Task execution failed");
            }

            const data = await res.json();
            setOutput((prev) => prev + `\n[${data.os}] Task completed.\nOUTPUT:\n${data.output}`);

            toast({
                title: "Task Executed",
                description: `Successfully executed ${task}`,
            });
        } catch (error: any) {
            setOutput((prev) => prev + `\nERROR: ${error.message}`);
            toast({
                variant: "destructive",
                title: "Execution Error",
                description: error.message,
            });
        } finally {
            setIsExecuting(false);
        }
    };

    return (
        <Card className="mb-4 bg-sidebar border-none shadow-none">
            <CardHeader className="pb-3 px-4 pt-0 mt-4">
                <div className="flex items-center gap-2">
                    <Terminal className="h-5 w-5 text-primary" />
                    <CardTitle className="text-lg font-medium">System Control Shell</CardTitle>
                </div>
                <CardDescription className="text-xs">
                    Securely execute whitelisted administrative tasks on the host machine.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 px-4 pb-2">
                <div className="space-y-2 relative z-10">
                    <Label className="text-xs">Wi-Fi Interface</Label>
                    <Select
                        value={interfaceName}
                        onValueChange={setInterfaceName}
                        disabled={isExecuting || availableInterfaces.length === 0}
                    >
                        <SelectTrigger className="h-8 text-xs w-full">
                            <SelectValue placeholder="Select interface..." />
                        </SelectTrigger>
                        <SelectContent>
                            {availableInterfaces.map((iface) => (
                                <SelectItem key={iface} value={iface} className="text-xs">
                                    {iface}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div className="grid grid-cols-2 gap-2 relative z-0">
                    {TASKS.map((t) => (
                        <Button
                            key={t.id}
                            variant={t.variant}
                            size="sm"
                            className="w-full text-xs justify-start h-8 px-2"
                            onClick={() => handleExecute(t.id)}
                            disabled={isExecuting}
                        >
                            {t.icon}
                            {t.label}
                        </Button>
                    ))}
                </div>

                <div className="rounded-md bg-black border border-white/20 p-2 h-48 overflow-y-auto">
                    <pre className="text-[10px] font-mono text-green-400 whitespace-pre-wrap leading-tight">
                        {output}
                    </pre>
                </div>
            </CardContent>
        </Card>
    );
}
