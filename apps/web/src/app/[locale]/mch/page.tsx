"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Heart,
  Baby,
  AlertTriangle,
  Calendar,
  Syringe,
  Users,
  Clock,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useMCHSummary,
  useANCProfiles,
  useChildRecords,
} from "@/hooks/useMCH";
import { cn } from "@/lib/utils";
import { PatientContextBar } from "@/components/patient/PatientContextBar";

/** Risk level badge styling. */
const RISK_STYLES: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  moderate: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** ANC status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  delivered: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  postnatal: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  closed: "bg-muted text-muted-foreground",
  transferred: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
};

/**
 * MCH Dashboard — shows ANC profiles, child health records, and summary stats.
 * Combines maternal and child health tracking.
 *
 * @returns MCH dashboard page
 */
export default function MCHDashboardPage() {
  const t = useTranslations("mch");
  const tc = useTranslations("common");
  const searchParams = useSearchParams();
  const patientId = searchParams?.get("patient") ?? "";
  const [tab, setTab] = useState<"anc" | "children">("anc");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: summary } = useMCHSummary();
  const { data: ancProfiles, isLoading: ancLoading } = useANCProfiles(
    tab === "anc" ? statusFilter || undefined : undefined
  );
  const { data: children, isLoading: childrenLoading } = useChildRecords();

  return (
    <div className="mx-auto max-w-6xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {patientId && <PatientContextBar patientId={patientId} className="mb-4" />}
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Heart className="h-7 w-7 text-pink-500" />
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        </div>
        <div className="flex items-center gap-3">
          {tab === "anc" && (
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
            >
              <option value="">{t("filterAll")}</option>
              <option value="active">{t("statusActive")}</option>
              <option value="delivered">{t("statusDelivered")}</option>
              <option value="postnatal">{t("statusPostnatal")}</option>
              <option value="closed">{t("statusClosed")}</option>
            </select>
          )}
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard
            icon={<Heart className="h-5 w-5 text-pink-500" />}
            label={t("activeANC")}
            value={String(summary.active_anc_profiles)}
          />
          <SummaryCard
            icon={<AlertTriangle className="h-5 w-5 text-red-500" />}
            label={t("highRisk")}
            value={String(summary.high_risk_pregnancies)}
            highlight={summary.high_risk_pregnancies > 0}
          />
          <SummaryCard
            icon={<Baby className="h-5 w-5 text-blue-500" />}
            label={t("deliveriesMonth")}
            value={String(summary.deliveries_this_month)}
          />
          <SummaryCard
            icon={<Baby className="h-5 w-5 text-green-500" />}
            label={t("liveBirths")}
            value={String(summary.live_births_this_month)}
          />
          <SummaryCard
            icon={<Users className="h-5 w-5 text-purple-500" />}
            label={t("activeChildren")}
            value={String(summary.active_children)}
          />
          <SummaryCard
            icon={<Syringe className="h-5 w-5 text-amber-500" />}
            label={t("overdueImmunizations")}
            value={String(summary.overdue_immunizations)}
            highlight={summary.overdue_immunizations > 0}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex border-b border-border">
        <button
          onClick={() => setTab("anc")}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-colors",
            tab === "anc"
              ? "border-b-2 border-pink-500 text-pink-600 dark:text-pink-400"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {t("antenatalCare")}
        </button>
        <button
          onClick={() => setTab("children")}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-colors",
            tab === "children"
              ? "border-b-2 border-blue-500 text-blue-600 dark:text-blue-400"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {t("childHealth")}
        </button>
      </div>

      {/* ANC Profiles tab */}
      {tab === "anc" && (
        <>
          {ancLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              {tc("loading")}
            </div>
          ) : !ancProfiles?.items.length ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Heart className="mb-3 h-12 w-12 opacity-40" />
              <p className="text-lg">{t("noANCProfiles")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {ancProfiles.items.map((profile) => (
                <Link
                  key={profile.id}
                  href={`/mch/${profile.id}`}
                  className={cn(
                    "flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:shadow-md",
                    profile.risk_level === "high" && "border-red-400 dark:border-red-700"
                  )}
                >
                  {/* Icon */}
                  <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300">
                    <Heart className="h-5 w-5" />
                  </div>

                  {/* Patient & ANC info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-semibold text-foreground">
                        {profile.patient_name ?? "—"}
                      </span>
                      {profile.patient_mrn && (
                        <span className="font-mono text-xs text-muted-foreground">
                          {profile.patient_mrn}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="font-mono">{profile.anc_number}</span>
                      <span>
                        G{profile.gravida}P{profile.parity}
                      </span>
                      {profile.gestation_weeks != null && (
                        <span>
                          {profile.gestation_weeks} {t("weeks")}
                        </span>
                      )}
                      <span>
                        {profile.visit_count} {t("visits")}
                      </span>
                    </div>
                  </div>

                  {/* EDD */}
                  {profile.expected_delivery_date && (
                    <div className="hidden flex-shrink-0 text-center sm:block">
                      <Calendar className="mx-auto h-4 w-4 text-muted-foreground" />
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {t("edd")}: {profile.expected_delivery_date}
                      </div>
                    </div>
                  )}

                  {/* Risk badge */}
                  <span
                    className={cn(
                      "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      RISK_STYLES[profile.risk_level] ?? RISK_STYLES.low
                    )}
                  >
                    {t(`risk_${profile.risk_level}` as "risk_low" | "risk_moderate" | "risk_high")}
                  </span>

                  {/* Status badge */}
                  <span
                    className={cn(
                      "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES[profile.status] ?? STATUS_STYLES.active
                    )}
                  >
                    {t(`status_${profile.status}` as "status_active" | "status_delivered" | "status_postnatal" | "status_closed")}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {/* Child Health tab */}
      {tab === "children" && (
        <>
          {childrenLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              {tc("loading")}
            </div>
          ) : !children?.items.length ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Baby className="mb-3 h-12 w-12 opacity-40" />
              <p className="text-lg">{t("noChildren")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {children.items.map((child) => (
                <div
                  key={child.id}
                  className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)]"
                >
                  {/* Icon */}
                  <div
                    className={cn(
                      "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full",
                      child.sex === "male"
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                        : "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300"
                    )}
                  >
                    <Baby className="h-5 w-5" />
                  </div>

                  {/* Child info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-semibold text-foreground">
                        {child.patient_name ?? "—"}
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {child.child_number}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                      <span>{t(child.sex as "male" | "female")}</span>
                      {child.age_months != null && (
                        <span>
                          {child.age_months} {t("months")}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Syringe className="h-3 w-3" />
                        {child.immunization_count} {t("doses")}
                      </span>
                      {child.hiv_exposed && (
                        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                          {t("hivExposed")}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* DOB */}
                  <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                    <Clock className="h-3 w-3" />
                    {t("dob")}: {child.date_of_birth}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Summary card for dashboard stats.
 *
 * @param props - Card props
 * @returns Summary card component
 */
function SummaryCard({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]",
        highlight && "border-amber-300 dark:border-amber-800"
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p
        className={cn(
          "mt-1 text-xl font-bold",
          highlight ? "text-amber-700 dark:text-amber-400" : "text-foreground"
        )}
      >
        {value}
      </p>
    </div>
  );
}
