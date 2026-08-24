"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { listProjects, checkHealth } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
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
  LogOut,
  User,
} from "lucide-react";

export default function DashboardPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectDashboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login");
    }
  }, [authLoading, user, router]);

  // Fetch projects once authenticated
  useEffect(() => {
    if (user) {
      fetchProjects();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function fetchProjects() {
    try {
      setLoading(true);
      setError(null);
      const data = await listProjects();
      setProjects(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to fetch projects";
      if (msg.includes("401")) {
        logout();
        router.push("/auth/login");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  // Show loading while checking auth
  if (authLoading || !user) {
    return (
      <AppShell>
        <div className="flex min-h-[80vh] items-center justify-center">
          <Skeleton className="h-8 w-48" />
        </div>
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
              Welcome back, {user.display_name || user.email}.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mr-2">
              <User className="size-4" />
              {user.email}
            </div>
            <Button variant="outline" size="sm" onClick={logout}>
              <LogOut className="mr-2 size-4" />
              Sign out
            </Button>
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
