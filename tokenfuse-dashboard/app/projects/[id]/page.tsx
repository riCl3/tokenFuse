"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { AppShell } from "@/components/app-shell";
import { getProject, getUsageSummary, updateProject, listPricing } from "@/lib/api-client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  formatCurrency,
  formatNumber,
  formatTokens,
  budgetPercent,
  statusColor,
} from "@/lib/format";
import type {
  ProjectResponse,
  UsageSummary,
} from "@/lib/api-types";
import {
  ArrowLeft,
  DollarSign,
  Zap,
  Activity,
  Clock,
  Copy,
  Check,
  Pencil,
  Trash2,
  Plus,
} from "lucide-react";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = Number(params.id);

  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [copiedKeyId, setCopiedKeyId] = useState<number | null>(null);
  const [showEdit, setShowEdit] = useState(false);
  const [editName, setEditName] = useState("");
  const [editBudget, setEditBudget] = useState("");
  const [editWarn, setEditWarn] = useState("0.8");
  const [editFallback, setEditFallback] = useState("");
  const [editOverrides, setEditOverrides] = useState<{ model: string; input: string; output: string }[]>([]);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [proj, usageData] = await Promise.all([
          getProject(projectId),
          getUsageSummary(projectId),
        ]);
        setProject(proj);
        setUsage(usageData);
      } catch {
        // Error handled by parent
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  function openEdit() {
    if (!project) return;
    setEditName(project.name);
    setEditBudget(project.monthly_budget_usd);
    setEditWarn(String(project.warn_pct));
    setEditFallback(project.fallback_model ?? "");
    const cp = project.custom_pricing;
    if (cp && typeof cp === "object") {
      setEditOverrides(
        Object.entries(cp).map(([model, v]) => ({ model, input: String((v as {input:number}).input), output: String((v as {output:number}).output) }))
      );
    } else {
      setEditOverrides([]);
    }
    setEditError(null);
    setShowEdit(true);
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    setEditLoading(true);
    setEditError(null);
    try {
      let customPricing: Record<string, { input: number; output: number }> | null = null;
      if (editOverrides.length > 0) {
        customPricing = {};
        for (const o of editOverrides) {
          if (!o.model.trim()) continue;
          customPricing[o.model.trim()] = { input: parseFloat(o.input), output: parseFloat(o.output) };
        }
        if (Object.keys(customPricing).length === 0) customPricing = null;
      }
      const updated = await updateProject(projectId, {
        name: editName.trim() || null,
        monthly_budget_usd: editBudget ? parseFloat(editBudget) : null,
        warn_pct: editWarn ? parseFloat(editWarn) : null,
        fallback_model: editFallback.trim() || null,
        custom_pricing: customPricing,
      });
      setProject(updated);
      // Refresh usage (window budget changes)
      const usageData = await getUsageSummary(projectId);
      setUsage(usageData);
      setShowEdit(false);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setEditLoading(false);
    }
  }

  function copyKeyId(id: number) {
    navigator.clipboard.writeText(`Project #${id}`);
    setCopiedKeyId(id);
    setTimeout(() => setCopiedKeyId(null), 2000);
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex flex-col gap-6">
          <Skeleton className="h-8 w-48" />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-64" />
        </div>
      </AppShell>
    );
  }

  if (!project || !usage) {
    return (
      <AppShell>
        <div className="flex flex-col items-center justify-center py-20">
          <p className="text-lg font-medium">Project not found</p>
          <Link href="/projects">
            <Button variant="link">Back to projects</Button>
          </Link>
        </div>
      </AppShell>
    );
  }

  const pct = budgetPercent(usage.window_used_units, usage.window_budget_units);

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div>
          <Link
            href="/projects"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Projects
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">
              {project.name}
            </h1>
            <Badge variant={statusColor(usage.window_status)}>
              {usage.window_status}
            </Badge>
            {!project.is_active && (
              <Badge variant="outline">inactive</Badge>
            )}
            <Button variant="outline" size="sm" onClick={openEdit} className="ml-2">
              <Pencil className="mr-2 size-3.5" /> Edit
            </Button>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Warning at {(project.warn_pct * 100).toFixed(0)}% • Fallback: {project.fallback_model ?? "none"} • Budget ${parseFloat(project.monthly_budget_usd).toFixed(2)}/mo
            {project.custom_pricing && Object.keys(project.custom_pricing).length > 0 && (
              <span> • {Object.keys(project.custom_pricing).length} custom price(s)</span>
            )}
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Total Spend
              </CardTitle>
              <DollarSign className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(usage.totals.total_cost_usd)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Total Tokens
              </CardTitle>
              <Zap className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatTokens(usage.totals.total_tokens)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">
                Total Requests
              </CardTitle>
              <Activity className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatNumber(usage.totals.total_requests)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Last 24h</CardTitle>
              <Clock className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(usage.last_24h_cost_usd)}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Budget Progress */}
        <Card>
          <CardHeader>
            <CardTitle>Budget Status</CardTitle>
            <CardDescription>
              Current window usage against monthly budget
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Progress value={pct} className="h-3 flex-1" />
              <span className="text-sm font-medium whitespace-nowrap">
                {pct.toFixed(1)}%
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {formatCurrency(project.monthly_budget_usd)}/mo budget •{" "}
              {pct.toFixed(0)}% used
            </p>
          </CardContent>
        </Card>

        {/* Usage by Model */}
        <Card>
          <CardHeader>
            <CardTitle>Usage by Model</CardTitle>
            <CardDescription>
              Token and cost breakdown per model.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {usage.by_model.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No usage data yet.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {usage.by_model.map((model) => (
                  <div
                    key={model.model}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex flex-col gap-1">
                      <span className="font-medium">{model.model}</span>
                      <span className="text-sm text-muted-foreground">
                        {formatNumber(model.requests)} requests •{" "}
                        {formatTokens(model.total_tokens)} tokens
                      </span>
                    </div>
                    <span className="font-semibold">
                      {formatCurrency(model.cost_usd)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Per-project pricing overrides summary */}
        {project.custom_pricing && Object.keys(project.custom_pricing).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Custom Pricing (project override)</CardTitle>
              <CardDescription>Takes precedence over global pricing for this project.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-[1fr_110px_110px] gap-2 text-xs font-medium text-muted-foreground">
                <span>Model</span><span>Input $/1M</span><span>Output $/1M</span>
              </div>
              {Object.entries(project.custom_pricing).map(([model, price]) => (
                <div key={model} className="grid grid-cols-[1fr_110px_110px] gap-2 text-sm border-t py-2">
                  <span className="font-mono text-xs">{model}</span>
                  <span>${Number((price as {input:number}).input).toFixed(4)}</span>
                  <span>${Number((price as {output:number}).output).toFixed(4)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* API Keys */}
        <Card>
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
            <CardDescription>
              Keys for authenticating requests to this project.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {project.api_keys.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No API keys yet.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {project.api_keys.map((key) => (
                  <div
                    key={key.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {key.label ?? `Key #${key.id}`}
                        </span>
                        <Badge
                          variant={key.is_active ? "default" : "outline"}
                        >
                          {key.is_active ? "active" : "revoked"}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        Created{" "}
                        {new Date(key.created_at).toLocaleDateString()}
                        {key.last_used_at &&
                          ` • Last used ${new Date(key.last_used_at).toLocaleDateString()}`}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyKeyId(key.id)}
                    >
                      {copiedKeyId === key.id ? (
                        <Check className="size-4" />
                      ) : (
                        <Copy className="size-4" />
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        </div>

        {/* Edit Dialog */}
        <Dialog open={showEdit} onOpenChange={setShowEdit}>
          <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Project</DialogTitle>
              <DialogDescription>Update budget, warning threshold, fallback model, and per-project pricing overrides.</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleEditSave} className="flex flex-col gap-4 py-2">
              <div className="flex flex-col gap-2">
                <Label>Name</Label>
                <Input value={editName} onChange={(e) => setEditName(e.target.value)} required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-2">
                  <Label>Monthly budget (USD)</Label>
                  <Input type="number" step="0.01" value={editBudget} onChange={(e) => setEditBudget(e.target.value)} />
                </div>
                <div className="flex flex-col gap-2">
                  <Label>Warning threshold</Label>
                  <Select value={editWarn} onValueChange={(v: string | null) => { if (v) setEditWarn(v); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0.5">50%</SelectItem>
                      <SelectItem value="0.6">60%</SelectItem>
                      <SelectItem value="0.7">70%</SelectItem>
                      <SelectItem value="0.8">80%</SelectItem>
                      <SelectItem value="0.85">85%</SelectItem>
                      <SelectItem value="0.9">90%</SelectItem>
                      <SelectItem value="0.95">95%</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Fallback model (optional)</Label>
                <Input placeholder="e.g. gpt-4o-mini" value={editFallback} onChange={(e) => setEditFallback(e.target.value)} />
              </div>
              {/* Per-project pricing */}
              <div className="rounded-lg border p-3">
                <p className="text-sm font-medium">Custom pricing overrides</p>
                <p className="text-xs text-muted-foreground mb-3">Override global prices for this project. USD per 1M tokens.</p>
                {editOverrides.length === 0 && <p className="text-xs italic text-muted-foreground">No overrides.</p>}
                {editOverrides.map((o, idx) => (
                  <div key={idx} className="grid grid-cols-[1fr_95px_95px_auto] gap-2 items-end mt-2">
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Model</Label>
                      <Input placeholder="gpt-4o" value={o.model} onChange={(e) => { const c=[...editOverrides]; c[idx].model=e.target.value; setEditOverrides(c); }} />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Input $/1M</Label>
                      <Input type="number" step="0.0001" value={o.input} onChange={(e) => { const c=[...editOverrides]; c[idx].input=e.target.value; setEditOverrides(c); }} />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Output $/1M</Label>
                      <Input type="number" step="0.0001" value={o.output} onChange={(e) => { const c=[...editOverrides]; c[idx].output=e.target.value; setEditOverrides(c); }} />
                    </div>
                    <Button type="button" variant="ghost" size="icon" onClick={() => setEditOverrides(editOverrides.filter((_, i) => i !== idx))}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => setEditOverrides([...editOverrides, { model: "", input: "", output: "" }])}>
                  <Plus className="mr-2 size-3" /> Add override
                </Button>
              </div>
              {editError && <p className="text-sm text-destructive">{editError}</p>}
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowEdit(false)}>Cancel</Button>
                <Button type="submit" disabled={editLoading}>{editLoading ? "Saving..." : "Save"}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </AppShell>
  );
}
