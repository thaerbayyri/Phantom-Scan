import { useState } from "react";
import { Settings, Target, ShieldCheck, Radar, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { ProcessingConfig } from "@shared/schema";

interface ControlPanelProps {
  config: ProcessingConfig;
  onConfigChange: (config: Partial<ProcessingConfig>) => void;
}

export function ControlPanel({ config, onConfigChange }: ControlPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={`border-r bg-sidebar overflow-y-auto transition-all duration-300 ease-in-out flex flex-col ${collapsed ? "w-12" : "w-80"
        }`}
    >
      {/* Toggle button */}
      <div className={`flex items-center ${collapsed ? "justify-center p-2" : "gap-2 p-4 pb-2"}`}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          title={collapsed ? "Expand panel" : "Collapse panel"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-5 w-5" />
          ) : (
            <PanelLeftClose className="h-5 w-5" />
          )}
        </button>
        {!collapsed && (
          <>
            <Settings className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-medium">Signal Processing</h2>
          </>
        )}
      </div>

      {/* Collapsed: show vertical icons only */}
      {collapsed && (
        <div className="flex flex-col items-center gap-3 pt-4">
          <span title="Clutter Removal"><ShieldCheck className="h-4 w-4 text-emerald-500" /></span>
          <span title="Motion Gate"><Radar className="h-4 w-4 text-amber-500" /></span>
          <span title="ISAR / MUSIC"><Target className="h-4 w-4 text-chart-2" /></span>
        </div>
      )}

      {/* Expanded: full accordion */}
      {!collapsed && (
        <div className="px-4 pb-4 flex-1">
          <Accordion
            type="multiple"
            defaultValue={["clutter", "motion", "isar"]}
            className="space-y-2"
          >
            {/* ── Clutter Removal ── */}
            <AccordionItem value="clutter" className="border-none">
              <Card>
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <CardHeader className="p-0 flex flex-row items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-emerald-500" />
                    <CardTitle className="text-sm">Clutter Removal</CardTitle>
                  </CardHeader>
                </AccordionTrigger>
                <AccordionContent>
                  <CardContent className="pt-2 space-y-4">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="clutter-enabled" className="text-sm">
                        Enable Background Subtraction
                      </Label>
                      <Switch
                        id="clutter-enabled"
                        checked={config.clutterRemovalEnabled}
                        onCheckedChange={(checked) =>
                          onConfigChange({ clutterRemovalEnabled: checked })
                        }
                        data-testid="switch-clutter-enabled"
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm">Window Size (N)</Label>
                        <span className="text-sm font-mono text-muted-foreground">
                          {config.clutterWindowSize}
                        </span>
                      </div>
                      <Slider
                        value={[config.clutterWindowSize]}
                        min={10}
                        max={200}
                        step={5}
                        onValueChange={([v]) =>
                          onConfigChange({ clutterWindowSize: v })
                        }
                        disabled={!config.clutterRemovalEnabled}
                        data-testid="slider-clutter-window"
                      />
                    </div>
                    <div className="text-xs text-muted-foreground p-2 bg-muted rounded-md">
                      Subtracts running average H̄(f) from each frame to isolate
                      dynamic reflections (moving objects) from static clutter
                      (walls/furniture).
                    </div>
                  </CardContent>
                </AccordionContent>
              </Card>
            </AccordionItem>

            {/* ── Motion Gate ── */}
            <AccordionItem value="motion" className="border-none">
              <Card>
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <CardHeader className="p-0 flex flex-row items-center gap-2">
                    <Radar className="h-4 w-4 text-amber-500" />
                    <CardTitle className="text-sm">Motion Gate</CardTitle>
                  </CardHeader>
                </AccordionTrigger>
                <AccordionContent>
                  <CardContent className="pt-2 space-y-4">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="motion-gate-enabled" className="text-sm">
                        Enable Motion Gating
                      </Label>
                      <Switch
                        id="motion-gate-enabled"
                        checked={config.motionGateEnabled}
                        onCheckedChange={(checked) =>
                          onConfigChange({ motionGateEnabled: checked })
                        }
                        data-testid="switch-motion-gate"
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm">Threshold η</Label>
                        <span className="text-sm font-mono text-muted-foreground">
                          {config.motionThreshold.toFixed(3)}
                        </span>
                      </div>
                      <Slider
                        value={[config.motionThreshold * 1000]}
                        min={0}
                        max={500}
                        step={1}
                        onValueChange={([v]) =>
                          onConfigChange({ motionThreshold: v / 1000 })
                        }
                        disabled={!config.motionGateEnabled}
                        data-testid="slider-motion-threshold"
                      />
                    </div>
                    <div className="text-xs text-muted-foreground p-2 bg-muted rounded-md">
                      Suppresses rendering when signal variance falls below threshold
                      η (empty room). Auto-calibrates from the first 100 "still"
                      samples.
                    </div>
                  </CardContent>
                </AccordionContent>
              </Card>
            </AccordionItem>



            {/* ── ISAR / MUSIC ── */}
            <AccordionItem value="isar" className="border-none">
              <Card>
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <CardHeader className="p-0 flex flex-row items-center gap-2">
                    <Target className="h-4 w-4 text-chart-2" />
                    <CardTitle className="text-sm">ISAR / MUSIC</CardTitle>
                  </CardHeader>
                </AccordionTrigger>
                <AccordionContent>
                  <CardContent className="pt-2 space-y-4">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="isar-enabled" className="text-sm">
                        Enable ISAR
                      </Label>
                      <Switch
                        id="isar-enabled"
                        checked={config.isarEnabled}
                        onCheckedChange={(checked) =>
                          onConfigChange({ isarEnabled: checked })
                        }
                        data-testid="switch-isar-enabled"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-sm">Array Length</Label>
                      <Input
                        type="number"
                        value={config.arrayLength}
                        min={2}
                        max={128}
                        onChange={(e) =>
                          onConfigChange({ arrayLength: parseInt(e.target.value) || 16 })
                        }
                        disabled={!config.isarEnabled}
                        data-testid="input-array-length"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-sm">AoA Range (degrees)</Label>
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          value={config.aoaRangeMin}
                          min={-90}
                          max={90}
                          onChange={(e) =>
                            onConfigChange({
                              aoaRangeMin: parseInt(e.target.value) || -60,
                            })
                          }
                          disabled={!config.isarEnabled}
                          className="w-20"
                          data-testid="input-aoa-min"
                        />
                        <span className="text-muted-foreground">to</span>
                        <Input
                          type="number"
                          value={config.aoaRangeMax}
                          min={-90}
                          max={90}
                          onChange={(e) =>
                            onConfigChange({
                              aoaRangeMax: parseInt(e.target.value) || 60,
                            })
                          }
                          disabled={!config.isarEnabled}
                          className="w-20"
                          data-testid="input-aoa-max"
                        />
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground p-2 bg-muted rounded-md">
                      MUSIC algorithm calculates AoA using consecutive time samples
                      as a spatial antenna array.
                    </div>
                  </CardContent>
                </AccordionContent>
              </Card>
            </AccordionItem>


          </Accordion>
        </div>
      )}
    </div>
  );
}
