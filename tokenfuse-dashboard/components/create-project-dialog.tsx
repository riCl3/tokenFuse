"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { createProject, setApiKey } from "@/lib/api-client";
import { Trash2, Plus } from "lucide-react";

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  openrouter: "OpenRouter",
  grok: "Grok (xAI)",
  groq: "Groq",
};

function buildProviderKeys(state: Record<string, string>): Record<string, string> | undefined {
  const cleaned: Record<string, string> = {};
  for (const [k, v] of Object.entries(state)) {
    if (v && v.trim()) cleaned[k] = v.trim();
  }
  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
}

interface CreateProjectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [warnPct, setWarnPct] = useState("0.8");
  const [fallbackModel, setFallbackModel] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [overrides, setOverrides] = useState<
    { model: string; input: string; output: string }[]
  >([]);
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({
    openai: "",
    openrouter: "",
    grok: "",
    groq: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  function resetForm() {
    setName("");
    setBudget("");
    setWarnPct("0.8");
    setFallbackModel("");
    setOverrides([]);
    setProviderKeys({ openai: "", openrouter: "", grok: "", groq: "" });
    setShowAdvanced(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    setError(null);

    try {
      // Build per-project custom_pricing dict
      let customPricing: Record<string, { input: number; output: number }> | undefined;
      if (overrides.length > 0) {
        customPricing = {};
        for (const o of overrides) {
          if (!o.model.trim()) continue;
          const inp = parseFloat(o.input);
          const out = parseFloat(o.output);
          if (isNaN(inp) || isNaN(out)) {
            throw new Error(`Invalid price for ${o.model}`);
          }
          customPricing[o.model.trim()] = { input: inp, output: out };
        }
        if (Object.keys(customPricing).length === 0) customPricing = undefined;
      }

      const result = await createProject({
        name: name.trim(),
        monthly_budget_usd: budget ? parseFloat(budget) : undefined,
        warn_pct: warnPct ? parseFloat(warnPct) : undefined,
        fallback_model: fallbackModel.trim() || undefined,
        custom_pricing: customPricing,
        provider_keys: buildProviderKeys(providerKeys),
      });
      // Store the API key from the first project
      if (result.api_key) {
        setApiKey(result.api_key);
      }
      setCreatedKey(result.api_key);
      resetForm();
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {createdKey ? (
          <>
            <DialogHeader>
              <DialogTitle>Project Created!</DialogTitle>
              <DialogDescription>
                Save your API key — it will only be shown once.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-3">
              <div className="rounded-lg bg-muted p-3">
                <p className="mb-1 text-xs font-medium text-muted-foreground">
                  API Key
                </p>
                <code className="break-all text-sm font-mono">{createdKey}</code>
              </div>
              <Button
                onClick={() => {
                  setCreatedKey(null);
                  onOpenChange(false);
                }}
                className="w-full"
              >
                Done
              </Button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>New Project</DialogTitle>
              <DialogDescription>
                Create a new project to track LLM usage and manage budgets.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-4 py-4 max-h-[60vh] overflow-y-auto pr-1">
              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Project Name</Label>
                <Input
                  id="name"
                  placeholder="My Chatbot"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="budget">Monthly Budget (USD)</Label>
                <Input
                  id="budget"
                  type="number"
                  step="0.01"
                  placeholder="50.00"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Leave empty for default ($50).
                </p>
              </div>

              {/* Warning threshold & Fallback */}
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-2">
                  <Label>Warning threshold</Label>
                  <Select value={warnPct} onValueChange={(v: string | null) => { if (v) setWarnPct(v); }}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0.5">50% of budget</SelectItem>
                      <SelectItem value="0.6">60%</SelectItem>
                      <SelectItem value="0.7">70%</SelectItem>
                      <SelectItem value="0.8">80% (default)</SelectItem>
                      <SelectItem value="0.85">85%</SelectItem>
                      <SelectItem value="0.9">90%</SelectItem>
                      <SelectItem value="0.95">95%</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">When to show warn header.</p>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="fallback">Fallback model</Label>
                  <Input
                    id="fallback"
                    placeholder="e.g. gpt-4o-mini"
                    value={fallbackModel}
                    onChange={(e) => setFallbackModel(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">Optional.</p>
                </div>
              </div>

              {/* Advanced: per-project pricing overrides */}
              <div className="rounded-lg border p-3">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex w-full items-center justify-between text-sm font-medium"
                >
                  Custom pricing overrides
                  <span className="text-xs text-muted-foreground">
                    {showAdvanced ? "Hide" : `${overrides.length} override${overrides.length !== 1 ? "s" : ""}`}
                  </span>
                </button>
                {showAdvanced && (
                  <div className="mt-3 flex flex-col gap-3">
                    <p className="text-xs text-muted-foreground">
                      Override token prices for this project only. Falls back to global pricing, then defaults.
                      Prices are USD per 1M tokens.
                    </p>
                    {overrides.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">No overrides. Add one below.</p>
                    )}
                    {overrides.map((o, idx) => (
                      <div key={idx} className="grid grid-cols-[1fr_90px_90px_auto] gap-2 items-end">
                        <div className="flex flex-col gap-1">
                          <Label className="text-xs">Model</Label>
                          <Input
                            placeholder="gpt-4o"
                            value={o.model}
                            onChange={(e) => {
                              const copy = [...overrides];
                              copy[idx].model = e.target.value;
                              setOverrides(copy);
                            }}
                          />
                        </div>
                        <div className="flex flex-col gap-1">
                          <Label className="text-xs">Input $/1M</Label>
                          <Input
                            type="number"
                            step="0.01"
                            placeholder="2.50"
                            value={o.input}
                            onChange={(e) => {
                              const copy = [...overrides];
                              copy[idx].input = e.target.value;
                              setOverrides(copy);
                            }}
                          />
                        </div>
                        <div className="flex flex-col gap-1">
                          <Label className="text-xs">Output $/1M</Label>
                          <Input
                            type="number"
                            step="0.01"
                            placeholder="10.00"
                            value={o.output}
                            onChange={(e) => {
                              const copy = [...overrides];
                              copy[idx].output = e.target.value;
                              setOverrides(copy);
                            }}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => setOverrides(overrides.filter((_, i) => i !== idx))}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setOverrides([...overrides, { model: "", input: "", output: "" }])}
                    >
                      <Plus className="mr-2 size-3" />
                      Add override
                    </Button>
                  </div>
                )}
              </div>

              {/* Provider API keys */}
              <div className="rounded-lg border p-3">
                <div className="flex w-full items-center justify-between text-sm font-medium">
                  <span>Provider API keys</span>
                  <span className="text-xs text-muted-foreground">
                    {Object.values(providerKeys).filter((v) => v).length} set
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Per-project credentials used when proxying to a provider. If empty, the
                  server&apos;s global key is used. Keys are masked after saving.
                </p>
                <div className="mt-3 grid grid-cols-1 gap-3">
                  {(Object.keys(PROVIDER_LABELS) as string[]).map((key) => (
                    <div key={key} className="flex flex-col gap-1">
                      <Label className="text-xs">{PROVIDER_LABELS[key]}</Label>
                      <Input
                        type="password"
                        autoComplete="off"
                        placeholder={`${key} API key`}
                        value={providerKeys[key] ?? ""}
                        onChange={(e) =>
                          setProviderKeys((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading || !name.trim()}>
                {loading ? "Creating..." : "Create Project"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
