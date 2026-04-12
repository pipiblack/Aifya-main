"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Calendar, CheckCircle, Clock, Users } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useDentalSummary, useDentalVisits, useDentalTreatmentPlans } from "@/hooks/useDental";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-muted text-muted-foreground",
  in_progress: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  draft: "bg-muted text-muted-foreground",
  approved: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2 })}`;
}

export default function DentalPage() {
  const t = useTranslations("dental");
  const [tab, setTab] = useState<"visits" | "treatments">("visits");

  const { data: summary, isLoading: summaryLoading } = useDentalSummary();
  const { data: visits, isLoading: visitsLoading } = useDentalVisits();
  const { data: plans } = useDentalTreatmentPlans();

  const summaryCards = [
    { label: t("totalPatients"), value: summary?.total_patients ?? 0, icon: Users, color: "text-blue-600 dark:text-blue-400" },
    { label: t("todayVisits"), value: summary?.today_visits ?? 0, icon: Calendar, color: "text-purple-600 dark:text-purple-400" },
    { label: t("pendingTreatments"), value: summary?.pending_treatments ?? 0, icon: Clock, color: "text-amber-600 dark:text-amber-400" },
    { label: t("completedToday"), value: summary?.completed_today ?? 0, icon: CheckCircle, color: "text-green-600 dark:text-green-400" },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-5 w-5", card.color)} />
              <span className="text-sm text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="flex gap-2 border-b border-border">
        {(["visits", "treatments"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t_
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`tab.${t_}`)}
          </button>
        ))}
      </div>

      {tab === "visits" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("visitNumber")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("dentist")}</th>
                <th className="px-4 py-3">{t("date")}</th>
                <th className="px-4 py-3">{t("procedure")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visitsLoading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td></tr>
              ) : !visits?.items.length ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("noRecords")}</td></tr>
              ) : (
                visits.items.map((v) => (
                  <tr key={v.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{v.visit_number}</td>
                    <td className="px-4 py-3 font-medium text-foreground">{v.patient_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{v.dentist_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{new Date(v.visit_date).toLocaleDateString()}</td>
                    <td className="max-w-[200px] truncate px-4 py-3 text-foreground">{v.chief_complaint || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[v.status])}>
                        {t(`status.${v.status}`)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "treatments" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("treatmentPlan")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("procedure")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!plans?.items.length ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-muted-foreground/70">{t("noRecords")}</td></tr>
              ) : (
                plans.items.map((p) => (
                  <tr key={p.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{p.plan_number}</td>
                    <td className="px-4 py-3 text-foreground">{p.patient_id}</td>
                    <td className="max-w-[200px] truncate px-4 py-3 text-foreground">{p.diagnosis || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[p.status])}>
                        {t(`status.${p.status}`)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
