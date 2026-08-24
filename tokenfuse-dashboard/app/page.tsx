"use client";

import { useEffect, useState } from "react";
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
import { CreateProjectDialog } from "@/components/create-project-dialog";
import {
  listProjects,
  getApiKey,
  setApiKey,
  clearApiKey,
  checkHealth,
} from "@/lib/api-client";
import {
  formatCurrency,
  formatNumber,
  formatTokens,
  budgetPercent,
  statusColor,
} from "@/lib/format";
import type { ProjectDashboardRow } from "@/lib/api-types";
import {
  Plus,
  Zap,
  DollarSign,
  Activity,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectDashboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [connected, setConnected] = useState(false);

  // Check if we have an API key stored
  useEffect(() => {
    const stored = getApiKey();
    if (stored) {
      setApiKeyInput(stored);
      fetchProjects();
    } else {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchProjects() {
    try {
      setLoading(true);
      setError(null);
      const data = await listProjects();
      setProjects(data);
      setConnected(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to fetch projects";
      // 401 means the stored key is invalid/expired — clear it so the user
      // isn't stuck in a loop and show a helpful message.
      if (msg.includes("401")) {
        clearApiKey();
        setConnected(false);
        setError("Invalid API key. Please create a project or enter a valid key.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  function handleConnect() {
    if (!apiKeyInput.trim()) return;
    setApiKey(apiKeyInput.trim());
    fetchProjects();
  }

  // Connection screen
  if (!connected && !loading) {
    return (
      <AppShell>
        <div className="flex min-h-[80vh] items-center justify-center">
          <Card className="w-full max-w-md">
            <CardHeader className="text-center">
              <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl bg-primary/10">
                <Zap className="size-6 text-primary" />
              </div>
              <CardTitle className="text-2xl">Welcome to TokenFuse</CardTitle>
              <CardDescription>
                Connect to your TokenFuse instance to manage projects and monitor
                usage.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium">API Key</label>
                  <input
                    type="password"
                    placeholder="tfsk_..."
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                </div>
                <Button onClick={handleConnect} className="w-full">
                  Connect
                </Button>
                {error && (
                  <p className="text-sm text-destructive text-center">{error}</p>
                )}
                <div className="relative py-1">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-card px-2 text-muted-foreground">Or</span>
                  </div>
                </div>
                <Button variant="outline" className="w-full" onClick={() => setShowCreateDialog(true)}>
                  <Plus className="mr-2 size-4" />
                  Create your first project
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                  No key yet? Create a project — your API key will be shown once.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
        <CreateProjectDialog
          open={showCreateDialog}
          onOpenChange={setShowCreateDialog}
          onCreated={() => {
            setShowCreateDialog(false);
            const stored = getApiKey();
            if (stored) {
              setApiKeyInput(stored);
              fetchProjects();
            }
          }}
        />
      </AppShell>
    );
  }

  // Summary stats
  const totalCost = projects.reduce(
    (sum, p) => sum + parseFloat(p.total_cost_usd),
    0,
  );
  const totalTokens = projects.reduce((sum, p) => sum + p.total_tokens, 0);
  const totalRequests = projects.reduce((sum, p) => sum + p.total_requests, 0);
  const warnings = projects.filter(
    (p) => p.window_status === "warn" || p.window_status === "exceeded",
  ).length;

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground">
              Monitor your LLM usage across all projects.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={fetchProjects} disabled={loading}>
              <Activity className="mr-2 size-4" />
              Refresh
            </Button>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-2 size-4" />
              New Project
            </Button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <Card className="border-destructive/50 bg-destructive/5">
            <CardContent className="flex items-center gap-2 py-3 text-sm text-destructive">
              <AlertTriangle className="size-4" />
              {error}
            </CardContent>
          </Card>
        )}

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
                {formatCurrency(totalCost)}
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
                {formatTokens(totalTokens)}
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
                {formatNumber(totalRequests)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Projects</CardTitle>
              <Zap className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{projects.length}</div>
              {warnings > 0 && (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                  {warnings} budget warning{warnings > 1 ? "s" : ""}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Projects Table */}
        <Card>
          <CardHeader>
            <CardTitle>Projects</CardTitle>
            <CardDescription>
              All projects and their current usage status.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex flex-col gap-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : projects.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Zap className="mb-4 size-10 text-muted-foreground/50" />
                <p className="text-lg font-medium">No projects yet</p>
                <p className="mb-4 text-sm text-muted-foreground">
                  Create your first project to start tracking LLM usage.
                </p>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="mr-2 size-4" />
                  Create Project
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {projects.map((project) => {
                  const pct = budgetPercent(
                    project.window_used_units,
                    project.window_budget_units,
                  );
                  return (
                    <Link
                      key={project.id}
                      href={`/projects/${project.id}`}
                      className="group flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50"
                    >
                      <div className="flex flex-1 flex-col gap-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium group-hover:text-primary">
                            {project.name}
                          </span>
                          <Badge variant={statusColor(project.window_status)}>
                            {project.window_status}
                          </Badge>
                          {!project.is_active && (
                            <Badge variant="outline">inactive</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span>
                            {formatCurrency(project.total_cost_usd)} spent
                          </span>
                          <span>
                            {formatNumber(project.total_requests)} requests
                          </span>
                          <span>
                            {formatTokens(project.total_tokens)} tokens
                          </span>
                          <span>
                            Budget: {formatCurrency(project.monthly_budget_usd)}/mo
                          </span>
                        </div>
                        <div className="mt-2 max-w-md">
                          <Progress value={pct} className="h-1.5" />
                          <p className="mt-1 text-xs text-muted-foreground">
                            {pct.toFixed(0)}% of budget used
                          </p>
                        </div>
                      </div>
                      <ExternalLink className="ml-4 size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                    </Link>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <CreateProjectDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={() => {
          setShowCreateDialog(false);
          fetchProjects();
        }}
      />
    </AppShell>
  );
}
