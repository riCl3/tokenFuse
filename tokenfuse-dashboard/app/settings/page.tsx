"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AppShell } from "@/components/app-shell";
import {
  getApiKey,
  setApiKey,
  clearApiKey,
  checkHealth,
  listPricing,
  createPricing,
  updatePricing,
  deletePricing,
} from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PricingRow } from "@/lib/api-types";
import { Key, Trash2, Check, X, Plus, DollarSign, Pencil } from "lucide-react";

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [apiKey, setApiKeyState] = useState("");
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState<{
    app: string;
    environment: string;
  } | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Pricing
  const [pricing, setPricing] = useState<PricingRow[]>([]);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [pricingError, setPricingError] = useState<string | null>(null);
  const [newModel, setNewModel] = useState("");
  const [newInput, setNewInput] = useState("");
  const [newOutput, setNewOutput] = useState("");
  const [editingModel, setEditingModel] = useState<string | null>(null);
  const [editInput, setEditInput] = useState("");
  const [editOutput, setEditOutput] = useState("");

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    const stored = getApiKey();
    if (stored) {
      setApiKeyState(stored);
    }
    if (user) {
      fetchPricing();
    }
  }, [user]);

  async function fetchPricing() {
    try {
      setPricingLoading(true);
      setPricingError(null);
      const data = await listPricing();
      setPricing(data);
    } catch (err) {
      setPricingError(err instanceof Error ? err.message : "Failed to load pricing");
    } finally {
      setPricingLoading(false);
    }
  }

  async function handleAddPricing(e: React.FormEvent) {
    e.preventDefault();
    if (!newModel.trim() || !newInput || !newOutput) return;
    try {
      setPricingError(null);
      await createPricing({ model: newModel.trim(), input_price: parseFloat(newInput), output_price: parseFloat(newOutput) });
      setNewModel("");
      setNewInput("");
      setNewOutput("");
      await fetchPricing();
    } catch (err) {
      setPricingError(err instanceof Error ? err.message : "Failed to add pricing");
    }
  }

  async function handleEditSave(model: string) {
    try {
      const payload: { input_price?: number; output_price?: number } = {};
      if (editInput) payload.input_price = parseFloat(editInput);
      if (editOutput) payload.output_price = parseFloat(editOutput);
      await updatePricing(model, payload);
      setEditingModel(null);
      await fetchPricing();
    } catch (err) {
      setPricingError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function handleDelete(model: string) {
    if (!confirm(`Delete pricing for "${model}"?`)) return;
    try {
      await deletePricing(model);
      await fetchPricing();
    } catch (err) {
      setPricingError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function testConnection() {
    try {
      setHealthError(null);
      const data = await checkHealth();
      setHealth(data);
    } catch (err) {
      setHealth(null);
      setHealthError(
        err instanceof Error ? err.message : "Connection failed",
      );
    }
  }

  function handleSave() {
    if (apiKey.trim()) {
      setApiKey(apiKey.trim());
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  }

  function handleClear() {
    clearApiKey();
    setApiKeyState("");
    setHealth(null);
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Configure your TokenFuse connection and preferences.
          </p>
        </div>

        {/* Connection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="size-5" />
              Connection
            </CardTitle>
            <CardDescription>
              Enter your TokenFuse API key to connect to the backend.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="settings-api-key">API Key</Label>
              <div className="flex gap-2">
                <Input
                  id="settings-api-key"
                  type="password"
                  placeholder="tfsk_..."
                  value={apiKey}
                  onChange={(e) => setApiKeyState(e.target.value)}
                  className="flex-1"
                />
                <Button onClick={handleSave} disabled={!apiKey.trim()}>
                  {saved ? (
                    <>
                      <Check className="mr-2 size-4" />
                      Saved
                    </>
                  ) : (
                    "Save"
                  )}
                </Button>
                {apiKey && (
                  <Button variant="outline" onClick={handleClear}>
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>
            </div>

            <Separator />

            <div className="flex flex-col gap-2">
              <Button
                variant="outline"
                onClick={testConnection}
                className="w-fit"
              >
                Test Connection
              </Button>
              {health && (
                <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400">
                  <Check className="size-4" />
                  Connected to {health.app} ({health.environment})
                </div>
              )}
              {healthError && (
                <div className="flex items-center gap-2 rounded-lg bg-destructive/5 p-3 text-sm text-destructive">
                  <X className="size-4" />
                  {healthError}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Pricing (global + per-project defaults) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="size-5" />
              Token Pricing
            </CardTitle>
            <CardDescription>
              Global USD per 1M tokens. Used for all projects unless a project overrides it. Changes affect future requests only.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!user ? (
              <p className="text-sm text-muted-foreground">Sign in to manage pricing.</p>
            ) : (
              <>
                {pricingError && (
                  <div className="rounded-lg bg-destructive/5 p-3 text-sm text-destructive">{pricingError}</div>
                )}
                {/* Add */}
                <form onSubmit={handleAddPricing} className="grid grid-cols-[1fr_110px_110px_auto] gap-2 items-end rounded-lg border p-3">
                  <div className="flex flex-col gap-1">
                    <Label className="text-xs">Model</Label>
                    <Input placeholder="e.g. gpt-4o" value={newModel} onChange={(e) => setNewModel(e.target.value)} required />
                  </div>
                  <div className="flex flex-col gap-1">
                    <Label className="text-xs">Input $/1M</Label>
                    <Input type="number" step="0.0001" placeholder="2.50" value={newInput} onChange={(e) => setNewInput(e.target.value)} required />
                  </div>
                  <div className="flex flex-col gap-1">
                    <Label className="text-xs">Output $/1M</Label>
                    <Input type="number" step="0.0001" placeholder="10.00" value={newOutput} onChange={(e) => setNewOutput(e.target.value)} required />
                  </div>
                  <Button type="submit" size="sm">
                    <Plus className="mr-1 size-4" /> Add
                  </Button>
                </form>

                {/* Table */}
                {pricingLoading ? (
                  <p className="text-sm text-muted-foreground">Loading…</p>
                ) : pricing.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No pricing configured.</p>
                ) : (
                  <div className="rounded-lg border overflow-hidden">
                    <div className="grid grid-cols-[1fr_110px_110px_90px] gap-2 bg-muted/50 p-2 text-xs font-medium">
                      <span>Model</span><span>Input $/1M</span><span>Output $/1M</span><span className="text-right">Actions</span>
                    </div>
                    {pricing.map((row) => (
                      <div key={row.model} className="grid grid-cols-[1fr_110px_110px_90px] gap-2 items-center border-t p-2 text-sm">
                        <span className="font-mono text-xs truncate">{row.model}</span>
                        {editingModel === row.model ? (
                          <>
                            <Input type="number" step="0.0001" value={editInput} onChange={(e) => setEditInput(e.target.value)} className="h-8" />
                            <Input type="number" step="0.0001" value={editOutput} onChange={(e) => setEditOutput(e.target.value)} className="h-8" />
                            <div className="flex gap-1 justify-end">
                              <Button size="sm" onClick={() => handleEditSave(row.model)} className="h-7 px-2"><Check className="size-3" /></Button>
                              <Button size="sm" variant="outline" onClick={() => setEditingModel(null)} className="h-7 px-2"><X className="size-3" /></Button>
                            </div>
                          </>
                        ) : (
                          <>
                            <span>${parseFloat(row.input_price).toFixed(4)}</span>
                            <span>${parseFloat(row.output_price).toFixed(4)}</span>
                            <div className="flex gap-1 justify-end">
                              <Button variant="ghost" size="icon" className="size-7" onClick={() => { setEditingModel(row.model); setEditInput(row.input_price); setEditOutput(row.output_price); }}>
                                <Pencil className="size-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="size-7" onClick={() => handleDelete(row.model)}>
                                <Trash2 className="size-3.5" />
                              </Button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Tip: per-project overrides (in the project detail page) take precedence over this global table, which itself takes precedence over the built-in defaults.
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Info */}
        <Card>
          <CardHeader>
            <CardTitle>About TokenFuse</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>
              TokenFuse is a reverse proxy for LLM API calls with built-in
              budget tracking, usage monitoring, and burn-rate alerts.
            </p>
            <p className="mt-2">
              This dashboard connects to your TokenFuse backend to display
              project data, usage statistics, and manage API keys.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
