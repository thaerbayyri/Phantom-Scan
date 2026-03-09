import { useState } from "react";
import { Cpu, Wifi, Radio } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";

export function HardwareConfig() {
    const [mode, setMode] = useState<"active" | "passive">("active");
    const [ssid, setSsid] = useState("");
    const [password, setPassword] = useState("");
    const [targetMac, setTargetMac] = useState("");
    const [channel, setChannel] = useState("1");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const { toast } = useToast();

    const handleConfigure = async () => {
        setIsSubmitting(true);
        try {
            const payload = mode === "active"
                ? { mode, ssid, password }
                : { mode, targetMac, channel: parseInt(channel, 10) };

            const res = await fetch("/api/esp32/configure", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error || "Configuration failed");
            }

            toast({
                title: "Configuration Deployed",
                description: `ESP32-S3 instructed to enter ${mode} mode.`,
            });
        } catch (error: any) {
            toast({
                variant: "destructive",
                title: "Configuration Error",
                description: error.message,
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <Card className="mb-4 bg-sidebar border-none shadow-none">
            <CardHeader className="pb-3 px-4 pt-0 mt-4">
                <div className="flex items-center gap-2">
                    <Cpu className="h-5 w-5 text-primary" />
                    <CardTitle className="text-lg font-medium">Hardware Node</CardTitle>
                </div>
                <CardDescription className="text-xs">
                    Remotely deploy network protocols to ESP32-S3.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 px-4 pb-2">
                <Tabs value={mode} onValueChange={(v) => setMode(v as "active" | "passive")}>
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="active" className="text-xs">
                            <Wifi className="w-3 h-3 mr-2" /> Active Pinger
                        </TabsTrigger>
                        <TabsTrigger value="passive" className="text-xs">
                            <Radio className="w-3 h-3 mr-2" /> Sniffer
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="active" className="space-y-3 mt-4">
                        <div className="space-y-1">
                            <Label className="text-xs">Target SSID</Label>
                            <Input
                                placeholder="e.g. WiFi_Network"
                                value={ssid}
                                onChange={(e) => setSsid(e.target.value)}
                                className="h-8 text-sm bg-background/50"
                            />
                        </div>
                        <div className="space-y-1">
                            <Label className="text-xs">Password</Label>
                            <Input
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="h-8 text-sm bg-background/50"
                            />
                        </div>
                        <p className="text-[10px] text-muted-foreground leading-tight">
                            ESP32 will authenticate to this AP to initiate bouncing ICMP ping packets to capture reflection.
                        </p>
                    </TabsContent>

                    <TabsContent value="passive" className="space-y-3 mt-4">
                        <div className="space-y-1">
                            <Label className="text-xs">Target MAC Address</Label>
                            <Input
                                placeholder="00:11:22:33:44:55"
                                value={targetMac}
                                onChange={(e) => setTargetMac(e.target.value)}
                                className="h-8 text-sm font-mono bg-background/50"
                            />
                        </div>
                        <div className="space-y-1">
                            <Label className="text-xs">802.11 Channel</Label>
                            <Input
                                type="number"
                                min={1}
                                max={14}
                                value={channel}
                                onChange={(e) => setChannel(e.target.value)}
                                className="h-8 text-sm bg-background/50"
                            />
                        </div>
                        <p className="text-[10px] text-muted-foreground leading-tight">
                            ESP32 drops into promiscuous monitor mode to sniff ambient CSI on this channel without authenticating.
                        </p>
                    </TabsContent>
                </Tabs>

                <Button
                    className="w-full"
                    size="sm"
                    onClick={handleConfigure}
                    disabled={isSubmitting}
                >
                    {isSubmitting ? "Deploying..." : "Deploy to Node"}
                </Button>
            </CardContent>
        </Card>
    );
}
