"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

/**
 * Premium KPI stat card with icon, value, label, trend, and subtitle.
 * Used across all dashboard pages for consistent metric display.
 *
 * @param icon - Lucide icon component
 * @param label - Metric label
 * @param value - Metric value (number or formatted string)
 * @param subtitle - Secondary info text
 * @param trend - Percentage change (positive = up, negative = down)
 * @param alert - Optional alert text (shown in red)
 * @param color - Icon background/text color variant
 * @param onClick - Optional click handler
 * @returns Premium stat card
 */
export function StatCard({
  icon: Icon,
  label,
  value,
  subtitle,
  trend,
  alert,
  color = "primary",
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  subtitle?: string;
  trend?: number;
  alert?: string;
  color?: "primary" | "blue" | "purple" | "amber" | "red" | "green" | "teal" | "cyan" | "orange" | "pink" | "indigo" | "emerald" | "violet" | "rose";
  onClick?: () => void;
}) {
  const colorMap: Record<string, { icon: string; bg: string }> = {
    primary: { icon: "text-primary", bg: "bg-primary/10" },
    blue: { icon: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950/50" },
    purple: { icon: "text-purple-600 dark:text-purple-400", bg: "bg-purple-50 dark:bg-purple-950/50" },
    amber: { icon: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950/50" },
    red: { icon: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950/50" },
    green: { icon: "text-green-600 dark:text-green-400", bg: "bg-green-50 dark:bg-green-950/50" },
    teal: { icon: "text-teal-600 dark:text-teal-400", bg: "bg-teal-50 dark:bg-teal-950/50" },
    cyan: { icon: "text-cyan-600 dark:text-cyan-400", bg: "bg-cyan-50 dark:bg-cyan-950/50" },
    orange: { icon: "text-orange-600 dark:text-orange-400", bg: "bg-orange-50 dark:bg-orange-950/50" },
    pink: { icon: "text-pink-600 dark:text-pink-400", bg: "bg-pink-50 dark:bg-pink-950/50" },
    indigo: { icon: "text-indigo-600 dark:text-indigo-400", bg: "bg-indigo-50 dark:bg-indigo-950/50" },
    emerald: { icon: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-950/50" },
    violet: { icon: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-950/50" },
    rose: { icon: "text-rose-600 dark:text-rose-400", bg: "bg-rose-50 dark:bg-rose-950/50" },
  };

  const c = colorMap[color] ?? colorMap.primary;

  return (
    <div
      className={cn(
        "group relative rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] transition-all duration-200",
        onClick && "cursor-pointer hover:shadow-[var(--shadow-card-hover)] hover:border-primary/20",
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", c.bg)}>
          <Icon className={cn("h-5 w-5", c.icon)} />
        </div>
        {trend !== undefined && (
          <div
            className={cn(
              "flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium",
              trend >= 0
                ? "bg-green-50 text-green-700 dark:bg-green-950/50 dark:text-green-400"
                : "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400"
            )}
          >
            {trend >= 0 ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold tabular-nums text-foreground">
          {value}
        </p>
        <p className="mt-0.5 text-xs font-medium text-muted-foreground">
          {label}
        </p>
      </div>
      {subtitle && (
        <p className="mt-1.5 text-xs text-muted-foreground/70">{subtitle}</p>
      )}
      {alert && (
        <p className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400">
          {alert}
        </p>
      )}
    </div>
  );
}

/**
 * Compact mini stat for secondary metrics.
 *
 * @param label - Label text
 * @param value - Metric value
 * @param color - Badge color variant
 * @returns Compact stat badge
 */
export function MiniStat({
  label,
  value,
  color = "default",
}: {
  label: string;
  value: string | number;
  color?: "default" | "green" | "amber" | "blue" | "red" | "purple";
}) {
  const styles: Record<string, string> = {
    default: "bg-muted text-muted-foreground",
    green: "bg-green-50 text-green-700 dark:bg-green-950/50 dark:text-green-400",
    amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
    blue: "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400",
    red: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400",
    purple: "bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-400",
  };

  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium", styles[color])}>
      <span className="font-semibold">{value}</span>
      {label}
    </span>
  );
}
