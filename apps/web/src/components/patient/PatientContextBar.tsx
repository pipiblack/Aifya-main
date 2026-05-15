"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, Droplets, Shield } from "lucide-react";
import { Avatar } from "@/components/ui/Avatar";
import { usePatient } from "@/hooks/usePatients";
import { cn } from "@/lib/utils";

interface PatientContextBarProps {
  /** Patient UUID to load; if empty/undefined the bar renders nothing. */
  patientId?: string;
  /** Extra classes for the outer container. */
  className?: string;
  /** Optional override children rendered on the right side. */
  rightContent?: React.ReactNode;
}

/**
 * Compute approximate age in whole years from an ISO date string.
 *
 * @param dob - Date of birth in ISO format (YYYY-MM-DD)
 * @returns Age in years, or null if dob is invalid
 */
function ageYears(dob: string | null | undefined): number | null {
  if (!dob) return null;
  const date = new Date(dob);
  if (Number.isNaN(date.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - date.getFullYear();
  const m = now.getMonth() - date.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < date.getDate())) age--;
  return age;
}

/**
 * Sticky patient context bar shared across clinical modules (Lab, Radiology,
 * Theatre, Dental, MCH, Referrals). Surfaces identity, demographics, blood
 * group, allergies and primary insurer so staff get the same overview no
 * matter which module they are in.
 *
 * Renders nothing when ``patientId`` is missing — pages should also offer
 * a patient picker when no patient is in context.
 *
 * @returns Sticky bar with patient context
 */
export function PatientContextBar({
  patientId,
  className,
  rightContent,
}: PatientContextBarProps) {
  const tc = useTranslations("common");
  const { data: patient, isLoading } = usePatient(patientId ?? "");

  if (!patientId) {
    return null;
  }

  if (isLoading || !patient) {
    return (
      <div
        className={cn(
          "sticky top-0 z-20 flex items-center gap-3 rounded-xl border border-border bg-card/80 px-4 py-2 text-sm shadow-[var(--shadow-card)] backdrop-blur",
          className,
        )}
      >
        <div className="h-10 w-10 animate-pulse rounded-full bg-muted" />
        <div className="flex-1 animate-pulse">
          <div className="h-3 w-32 rounded bg-muted" />
          <div className="mt-2 h-3 w-48 rounded bg-muted/70" />
        </div>
      </div>
    );
  }

  const fullName = [patient.first_name, patient.middle_name, patient.last_name]
    .filter(Boolean)
    .join(" ");
  const age = ageYears(patient.date_of_birth);
  const allergies = (patient.allergies ?? []).filter(Boolean);
  const insurer =
    patient.insurance_provider ||
    (patient.sha_number ? `SHA · ${patient.sha_number}` : null);

  return (
    <div
      data-tour="patient-context-bar"
      className={cn(
        "sticky top-0 z-20 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card/80 px-4 py-2 text-sm shadow-[var(--shadow-card)] backdrop-blur",
        className,
      )}
    >
      <Avatar name={fullName || patient.mrn} size="md" />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
          <span className="truncate font-semibold text-foreground">
            {fullName || tc("unknown")}
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            {patient.mrn}
          </span>
          {age !== null && (
            <span className="text-xs text-muted-foreground">
              {age} {tc("yearsShort") || "y"}
            </span>
          )}
          <span className="text-xs uppercase text-muted-foreground">
            {patient.gender}
          </span>
        </div>

        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {patient.blood_group && (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 font-medium text-rose-700 dark:bg-rose-950 dark:text-rose-300">
              <Droplets className="h-3 w-3" />
              {patient.blood_group}
            </span>
          )}
          {allergies.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
              <AlertTriangle className="h-3 w-3" />
              {allergies.slice(0, 3).join(", ")}
              {allergies.length > 3 && ` +${allergies.length - 3}`}
            </span>
          )}
          {insurer && (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              <Shield className="h-3 w-3" />
              {insurer}
            </span>
          )}
        </div>
      </div>

      {rightContent && (
        <div className="flex-shrink-0 text-right">{rightContent}</div>
      )}
    </div>
  );
}
