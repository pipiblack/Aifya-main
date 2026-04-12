"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  BeakerIcon,
  Brain,
  CheckCircle,
  ClipboardList,
  Clock,
  FlaskConical,
  Search,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useTrialsSummary, useTrials, useAdverseEvents, useAIScreenings } from "@/hooks/useClinicalTrials";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  setup: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  recruiting: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  active: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  follow_up: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  completed: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  suspended: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  terminated: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  withdrawn: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
};

const PARTICIPANT_STATUS_STYLES: Record<string, string> = {
  screened: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  enrolled: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  active: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  screen_failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  completed: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  withdrawn: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  lost_to_followup: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
};

type TabKey = "registry" | "adverse_events" | "ai_screening";

/**
 * Clinical Trials registry page.
 * ICH-GCP compliant trial management with AI screening and SAE tracking.
 *
 * @returns Clinical Trials page component
 */
export default function ClinicalTrialsPage() {
  const t = useTranslations("trials");
  const [tab, setTab] = useState<TabKey>("registry");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  const { data: summary, isLoading: summaryLoading } = useTrialsSummary();
  const { data: trials, isLoading: trialsLoading } = useTrials(statusFilter || undefined);
  const { data: adverseEvents, isLoading: aeLoading } = useAdverseEvents("", false);
  const { data: aiScreenings, isLoading: screeningLoading } = useAIScreenings("", true);

  const summaryCards = [
    { label: t("totalTrials"), value: summary?.total_trials ?? 0, icon: FlaskConical, color: "text-blue-600 dark:text-blue-400" },
    { label: t("recruiting"), value: summary?.recruiting_trials ?? 0, icon: UserPlus, color: "text-emerald-600 dark:text-emerald-400" },
    { label: t("activeTrials"), value: summary?.active_trials ?? 0, icon: Activity, color: "text-green-600 dark:text-green-400" },
    { label: t("completedTrials"), value: summary?.completed_trials ?? 0, icon: CheckCircle, color: "text-teal-600 dark:text-teal-400" },
    { label: t("totalParticipants"), value: summary?.total_participants ?? 0, icon: Users, color: "text-purple-600 dark:text-purple-400" },
    { label: t("enrolled"), value: summary?.enrolled_participants ?? 0, icon: ClipboardList, color: "text-indigo-600 dark:text-indigo-400" },
    { label: t("adverseEvents"), value: summary?.total_adverse_events ?? 0, icon: AlertTriangle, color: "text-amber-600 dark:text-amber-400" },
    { label: t("saeCount"), value: summary?.serious_adverse_events ?? 0, icon: XCircle, color: "text-red-600 dark:text-red-400" },
    { label: t("pendingScreenings"), value: summary?.pending_ai_screenings ?? 0, icon: Brain, color: "text-cyan-600 dark:text-cyan-400" },
    { label: t("screenFailures"), value: summary?.screen_failures ?? 0, icon: Clock, color: "text-orange-600 dark:text-orange-400" },
  ];

  const filteredTrials = trials?.items.filter((trial) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      trial.title.toLowerCase().includes(q) ||
      trial.trial_code.toLowerCase().includes(q) ||
      trial.sponsor.toLowerCase().includes(q) ||
      (trial.therapeutic_area?.toLowerCase().includes(q) ?? false)
    );
  });

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5 lg:grid-cols-10">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-1 text-lg font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {(["registry", "adverse_events", "ai_screening"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t_
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t(`tab.${t_}`)}
          </button>
        ))}
      </div>

      {/* Registry Tab */}
      {tab === "registry" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder={t("searchPlaceholder")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-border bg-card py-2 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
            >
              <option value="">{t("allStatuses")}</option>
              {["setup", "recruiting", "active", "follow_up", "completed", "suspended", "terminated"].map((s) => (
                <option key={s} value={s}>
                  {t(`trialStatus.${s}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Trial Table */}
          <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("trialCode")}</th>
                  <th className="px-4 py-3">{t("trialTitle")}</th>
                  <th className="px-4 py-3">{t("phase")}</th>
                  <th className="px-4 py-3">{t("sponsor")}</th>
                  <th className="px-4 py-3">{t("therapeuticArea")}</th>
                  <th className="px-4 py-3">{t("enrollment")}</th>
                  <th className="px-4 py-3">{t("statusLabel")}</th>
                  <th className="px-4 py-3">{t("dates")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {trialsLoading ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                      {t("loading")}
                    </td>
                  </tr>
                ) : !filteredTrials?.length ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                      {t("noTrials")}
                    </td>
                  </tr>
                ) : (
                  filteredTrials.map((trial) => (
                    <tr key={trial.id} className="bg-card hover:bg-muted/50">
                      <td className="px-4 py-3">
                        <Link
                          href={`/trials/${trial.id}`}
                          className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {trial.trial_code}
                        </Link>
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 font-medium text-foreground">
                        {trial.short_title || trial.title}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {trial.phase ? t(`phase.${trial.phase}`) : "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{trial.sponsor}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {trial.therapeutic_area || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-medium text-foreground">{trial.enrolled_count}</span>
                        {trial.target_enrollment && (
                          <span className="text-muted-foreground">
                            /{trial.target_enrollment}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium",
                            STATUS_STYLES[trial.status],
                          )}
                        >
                          {t(`trialStatus.${trial.status}`)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {trial.start_date
                          ? new Date(trial.start_date).toLocaleDateString()
                          : "—"}
                        {trial.end_date && (
                          <>
                            {" → "}
                            {new Date(trial.end_date).toLocaleDateString()}
                          </>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Adverse Events Tab */}
      {tab === "adverse_events" && (
        <div className="rounded-xl border border-border p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-3 pb-4">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <h2 className="text-lg font-semibold text-foreground">{t("tab.adverse_events")}</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("aeSelectTrial")}
          </p>
          <p className="mt-2 text-xs text-red-600 dark:text-red-400">
            {t("saeWarning")}
          </p>
        </div>
      )}

      {/* AI Screening Tab */}
      {tab === "ai_screening" && (
        <div className="rounded-xl border border-border p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-3 pb-4">
            <Brain className="h-5 w-5 text-cyan-500" />
            <h2 className="text-lg font-semibold text-foreground">{t("tab.ai_screening")}</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            {t("aiScreeningDescription")}
          </p>
          <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
            {t("aiDisclaimer")}
          </p>
        </div>
      )}
    </div>
  );
}
