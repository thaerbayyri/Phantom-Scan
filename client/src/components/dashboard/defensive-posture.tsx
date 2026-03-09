import { useState, useEffect } from "react";
import { ShieldAlert, Users, Activity, Play, Square, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";

interface DefensePosture {
    require_802_1x: boolean;
    disable_wpa3_transition_mode: boolean;
    radius_logging_enabled: boolean;
    pmf_required: boolean;
    crowd_count: number;
    is_scanning: boolean;
}

export function DefensivePosture() {
    const [posture, setPosture] = useState<DefensePosture | null>(null);
    const [interfaceName, setInterfaceName] = useState("wlan0");
    const [availableInterfaces, setAvailableInterfaces] = useState<string[]>(["wlan0"]);
    const { toast } = useToast();

    const fetchPosture = () => {
        fetch("/api/v1/defense/architecture")
            .then((res) => res.json())
            .then((data) => setPosture(data))
            .catch((err) => console.error("Failed to load defense posture", err));
    };

    useEffect(() => {
        fetchPosture();
        const interval = setInterval(fetchPosture, 2000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        fetch("/api/v1/system/interfaces")
            .then((res) => res.json())
            .then((data) => {
                if (data.interfaces && Array.isArray(data.interfaces)) {
                    const wifiIfaces = data.interfaces.filter((name: string) => {
                        const n = name.toLowerCase();
                        return n.includes("wlan") || n.includes("wi-fi") || n.includes("wireless") || n.startsWith("wl") || n === "wifi";
                    });
                    const options = wifiIfaces.length > 0 ? wifiIfaces : data.interfaces;
                    setAvailableInterfaces(options);
                    if (!options.includes("wlan0") && options.length > 0) {
                        setInterfaceName(options[0]);
                    } else if (options.includes("wlan0")) {
                        setInterfaceName("wlan0");
                    }
                }
            })
            .catch((err) => console.error("Failed to load interfaces:", err));
    }, []);

    const handleStart = async () => {
        try {
            const res = await fetch("/api/v1/defense/passive/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ interfaceName })
            });
            if (!res.ok) throw new Error("Failed to start scanner");
            toast({ title: "Passive Scanner Started", description: "Telemetry tracking active." });
            fetchPosture();
        } catch (e: any) {
            toast({ variant: "destructive", title: "Error", description: e.message });
        }
    };

    const handleStop = async () => {
        try {
            const res = await fetch("/api/v1/defense/passive/stop", { method: "POST" });
            if (!res.ok) throw new Error("Failed to stop scanner");
            toast({ title: "Passive Scanner Stopped", description: "Telemetry tracking halted." });
            fetchPosture();
        } catch (e: any) {
            toast({ variant: "destructive", title: "Error", description: e.message });
        }
    };

    if (!posture) return null;

    return (
        <Card className="bg-sidebar border-none shadow-none">
            <CardHeader className="pb-3 px-4 pt-4">
                <div className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5 text-emerald-500" />
                    <CardTitle className="text-lg font-medium">802.1X Defensive Architecture</CardTitle>
                </div>
                <CardDescription className="text-xs">
                    WPA3-Enterprise posture verification and anonymous passive environmental telemetry.
                </CardDescription>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-4">
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex justify-between items-center p-2 bg-black/20 rounded border border-white/5">
                        <span className="text-muted-foreground flex items-center gap-1"><Info className="h-3 w-3" /> Require 802.1X</span>
                        <Badge variant={posture.require_802_1x ? "default" : "destructive"} className="h-5 px-1.5 text-[10px]">
                            {posture.require_802_1x ? "ENFORCED" : "FAILURE"}
                        </Badge>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-black/20 rounded border border-white/5">
                        <span className="text-muted-foreground flex items-center gap-1"><Info className="h-3 w-3" /> PMF Required</span>
                        <Badge variant={posture.pmf_required ? "default" : "destructive"} className="h-5 px-1.5 text-[10px]">
                            {posture.pmf_required ? "ENFORCED" : "FAILURE"}
                        </Badge>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-black/20 rounded border border-white/5">
                        <span className="text-muted-foreground flex items-center gap-1"><Info className="h-3 w-3" /> Transition Mode</span>
                        <Badge variant={posture.disable_wpa3_transition_mode ? "default" : "destructive"} className="h-5 px-1.5 text-[10px]">
                            {posture.disable_wpa3_transition_mode ? "DISABLED" : "WARNING"}
                        </Badge>
                    </div>
                    <div className="flex justify-between items-center p-2 bg-black/20 rounded border border-white/5">
                        <span className="text-muted-foreground flex items-center gap-1"><Info className="h-3 w-3" /> RADIUS Logging</span>
                        <Badge variant={posture.radius_logging_enabled ? "default" : "destructive"} className="h-5 px-1.5 text-[10px]">
                            {posture.radius_logging_enabled ? "ACTIVE" : "FAILURE"}
                        </Badge>
                    </div>
                </div>

                <div className="h-px bg-border my-4"></div>

                <div className="flex items-center justify-between p-3 bg-black/30 rounded-lg border border-white/10 relative overflow-hidden">
                    <div className="flex items-center gap-3 z-10">
                        <div className={`p-2 rounded-full ${posture.is_scanning ? "bg-emerald-500/20 text-emerald-500" : "bg-muted text-muted-foreground"}`}>
                            <Users className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Crowd Count (Unique MACs)</p>
                            <div className="flex items-end gap-2">
                                <p className="text-2xl font-bold font-mono">{posture.crowd_count}</p>
                                {posture.is_scanning && <span className="text-[10px] text-emerald-500 mb-1 animate-pulse">Scanning...</span>}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-3 pt-2">
                    <div className="space-y-1">
                        <Label className="text-[10px] text-muted-foreground uppercase tracking-widest">Scanner Interface</Label>
                        <Select value={interfaceName} onValueChange={setInterfaceName} disabled={posture.is_scanning || availableInterfaces.length === 0}>
                            <SelectTrigger className="h-8 text-xs">
                                <SelectValue placeholder="Select interface..." />
                            </SelectTrigger>
                            <SelectContent>
                                {availableInterfaces.map(iface => (
                                    <SelectItem key={iface} value={iface} className="text-xs">{iface}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="flex gap-2">
                        {!posture.is_scanning ? (
                            <Button size="sm" className="w-full text-xs gap-1" onClick={handleStart}>
                                <Play className="h-3 w-3" /> Start Passive Telemetry
                            </Button>
                        ) : (
                            <Button size="sm" variant="destructive" className="w-full text-xs gap-1" onClick={handleStop}>
                                <Square className="h-3 w-3" /> Stop Scanner
                            </Button>
                        )}
                    </div>
                </div>

            </CardContent>
        </Card>
    );
}
