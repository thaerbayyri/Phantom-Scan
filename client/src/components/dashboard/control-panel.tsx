import { Settings, Target, Hand, Gauge } from "lucide-react";
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
  return (
    <div className="w-80 border-r bg-sidebar p-4 overflow-y-auto">
      <div className="flex items-center gap-2 mb-4">
        <Settings className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-medium">Signal Processing</h2>
      </div>

      <Accordion
        type="multiple"
        defaultValue={["nulling", "isar", "gesture"]}
        className="space-y-2"
      >
        <AccordionItem value="nulling" className="border-none">
          <Card>
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <CardHeader className="p-0 flex flex-row items-center gap-2">
                <Gauge className="h-4 w-4 text-chart-1" />
                <CardTitle className="text-sm">Nulling Engine</CardTitle>
              </CardHeader>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="pt-2 space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="nulling-enabled" className="text-sm">
                    Enable Nulling
                  </Label>
                  <Switch
                    id="nulling-enabled"
                    checked={config.nullingEnabled}
                    onCheckedChange={(checked) =>
                      onConfigChange({ nullingEnabled: checked })
                    }
                    data-testid="switch-nulling-enabled"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">Threshold (dB)</Label>
                    <span className="text-sm font-mono text-muted-foreground">
                      {config.nullingThreshold}
                    </span>
                  </div>
                  <Slider
                    value={[config.nullingThreshold]}
                    min={0}
                    max={100}
                    step={1}
                    onValueChange={([v]) =>
                      onConfigChange({ nullingThreshold: v })
                    }
                    disabled={!config.nullingEnabled}
                    data-testid="slider-nulling-threshold"
                  />
                </div>
                <div className="text-xs text-muted-foreground p-2 bg-muted rounded-md">
                  Computes p = -h1/h2 to subtract static reflections using
                  iterative nulling algorithm.
                </div>
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>

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

        <AccordionItem value="gesture" className="border-none">
          <Card>
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <CardHeader className="p-0 flex flex-row items-center gap-2">
                <Hand className="h-4 w-4 text-chart-3" />
                <CardTitle className="text-sm">Gesture Recognition</CardTitle>
              </CardHeader>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="pt-2 space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="gesture-enabled" className="text-sm">
                    Enable Gestures
                  </Label>
                  <Switch
                    id="gesture-enabled"
                    checked={config.gestureEnabled}
                    onCheckedChange={(checked) =>
                      onConfigChange({ gestureEnabled: checked })
                    }
                    data-testid="switch-gesture-enabled"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">Centroid Threshold</Label>
                    <span className="text-sm font-mono text-muted-foreground">
                      {config.centroidThreshold}
                    </span>
                  </div>
                  <Slider
                    value={[config.centroidThreshold]}
                    min={0}
                    max={50}
                    step={1}
                    onValueChange={([v]) =>
                      onConfigChange({ centroidThreshold: v })
                    }
                    disabled={!config.gestureEnabled}
                    data-testid="slider-centroid-threshold"
                  />
                </div>
                <div className="text-xs text-muted-foreground p-2 bg-muted rounded-md">
                  <strong>Bit 0:</strong> Step forward then backward<br />
                  <strong>Bit 1:</strong> Step backward then forward<br />
                  Detected via spatial centroid shift in matched filter.
                </div>
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
