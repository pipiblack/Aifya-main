"use client";

import { use } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Stethoscope,
  Clock,
  User,
  CheckCircle2,
  LogOut as DischargeIcon,
  BedDouble,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useEncounter, useUpdateEncounter } from "@/hooks/useEncounters";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { VitalsPanel } from "@/components/opd/VitalsPanel";
import { DiagnosisPanel } from "@/components/opd/DiagnosisPanel";
import { PrescriptionPanel } from "@/components/opd/PrescriptionPanel";
import { LabOrderPanel } from "@/components/opd/LabOrderPanel";
import { ScribeButton } from "@/components/opd/ScribeButton";

const TRIAGE_BADGE: Record<string, string> = {
  emergency: "bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
  urgent: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-950 dark:text-orange-200 dark:border-orange-800",
  standard: "bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-950 dark:text-yellow-200 dark:border-yellow-800",
  non_urgent: "bg-green-100 text-green-800 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-800",
  dead: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-200 dark:border-blue-800",
};

/**
 * OPD Consultation page — the main clinical workspace.
 * Panels: vitals, diagnosis (ICD-10), prescriptions (with KEML), lab orders.
 * ScribeAI button for ambient recording. 3-click rule for clinical actions.
 *
 * @returns Consultation page
 */
export default function ConsultationPage({
  params,
}: {
  params: Promise<{ encounterId: string }>;
}) {
  const { encounterId } = use(params);
  const t = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();

  const { data: encounter, isLoading } = useEncounter(encounterId);
  const updateEncounter = useUpdateEncounter(encounterId);

  const handleDisposition = (disposition: string, status: string) => {
    updateEncounter.mutate(
      { status: status as "completed" | "admitted" | "discharged", disposition: disposition as "discharged" | "admitted" | "referred" | "follow_up" | "deceased" },
      {
        onSuccess: () => {
          router.push("/opd");
        },
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!encounter) {
    return (
      <div className="p-6">
        <Link href="/opd" className="flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <p className="mt-4 text-muted-foreground">{t("notFound")}</p>
      </div>
    );
  }

  const triageClass = TRIAGE_BADGE[encounter.triage_category ?? "non_urgent"] ?? TRIAGE_BADGE.non_urgent;

  return (
    <div className="mx-auto max-w-5xl p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="mb-6">
        <Link href="/opd" className="mb-3 inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          {t("queue")}
        </Link>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Stethoscope className="h-6 w-6 text-primary" />
              <h1 className="text-xl font-bold text-foreground">
                {t("consultation")}
              </h1>
              {encounter.queue_number && (
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-sm font-mono font-medium text-muted-foreground">
                  #{encounter.queue_number}
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <User className="h-3.5 w-3.5" />
                {encounter.patient_name ?? encounter.patient_id}
              </span>
              {encounter.patient_mrn && (
                <span className="font-mono">{encounter.patient_mrn}</span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {formatDateTime(encounter.encounter_date)}
              </span>
              {encounter.triage_category && (
                <span className={cn("rounded-full border px-2 py-0.5 text-xs font-medium", triageClass)}>
                  {encounter.triage_category.replace("_", " ")}
                </span>
              )}
            </div>
            {encounter.chief_complaint && (
              <p className="mt-1 text-sm text-foreground">
                <span className="font-medium">{t("chiefComplaint")}:</span>{" "}
                {encounter.chief_complaint}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ScribeAI */}
      <div className="mb-4">
        <ScribeButton encounterId={encounterId} />
      </div>

      {/* Clinical panels */}
      <div className="space-y-4">
        <VitalsPanel encounterId={encounterId} patientId={encounter.patient_id} />
        <DiagnosisPanel encounterId={encounterId} patientId={encounter.patient_id} />
        <PrescriptionPanel encounterId={encounterId} patientId={encounter.patient_id} />
        <LabOrderPanel encounterId={encounterId} patientId={encounter.patient_id} />
      </div>

      {/* Disposition actions */}
      <div className="mt-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <h3 className="mb-3 font-semibold text-foreground">{t("disposition")}</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => handleDisposition("discharged", "completed")}
            disabled={updateEncounter.isPending}
            className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            <CheckCircle2 className="h-4 w-4" />
            {t("dischargeHome")}
          </button>
          <button
            onClick={() => handleDisposition("admitted", "admitted")}
            disabled={updateEncounter.isPending}
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            <BedDouble className="h-4 w-4" />
            {t("admitInpatient")}
          </button>
          <button
            onClick={() => handleDisposition("referred", "completed")}
            disabled={updateEncounter.isPending}
            className="flex items-center gap-2 rounded-lg border border-input bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            <DischargeIcon className="h-4 w-4" />
            {t("referOut")}
          </button>
          <button
            onClick={() => handleDisposition("follow_up", "completed")}
            disabled={updateEncounter.isPending}
            className="flex items-center gap-2 rounded-lg border border-input bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            <Clock className="h-4 w-4" />
            {t("scheduleFollowUp")}
          </button>
        </div>
      </div>
    </div>
  );
}
