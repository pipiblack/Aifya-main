"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, Siren } from "lucide-react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "@/i18n/routing";
import { useRegisterEmergencyVisit } from "@/hooks/useEmergency";
import type { ArrivalMode } from "@aifya/shared";

/** Zod schema for emergency visit registration form. */
const emergencyRegisterSchema = z.object({
  patient_id: z.string().uuid("Must be a valid UUID"),
  chief_complaint: z.string().min(3, "Chief complaint must be at least 3 characters"),
  arrival_mode: z.enum(["walk_in", "ambulance", "referral", "police", "other"]).optional(),
  brought_by: z.string().optional(),
  is_trauma: z.boolean().optional(),
  allergies_noted: z.string().optional(),
  notes: z.string().optional(),
});

type EmergencyRegisterFormValues = z.infer<typeof emergencyRegisterSchema>;

export default function RegisterEmergencyPage() {
  const t = useTranslations("emergency");
  const router = useRouter();
  const registerMutation = useRegisterEmergencyVisit();

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<EmergencyRegisterFormValues>({
    resolver: zodResolver(emergencyRegisterSchema),
    defaultValues: {
      patient_id: "",
      chief_complaint: "",
      arrival_mode: "walk_in",
      brought_by: "",
      is_trauma: false,
      allergies_noted: "",
      notes: "",
    },
    mode: "onChange",
  });

  const arrivalModes: ArrivalMode[] = ["walk_in", "ambulance", "referral", "police", "other"];

  const onSubmit = (data: EmergencyRegisterFormValues) => {
    registerMutation.mutate(
      {
        patient_id: data.patient_id,
        arrival_mode: data.arrival_mode ?? "walk_in",
        brought_by: data.brought_by || null,
        chief_complaint: data.chief_complaint,
        is_trauma: data.is_trauma ?? false,
        allergies_noted: data.allergies_noted || null,
        notes: data.notes || null,
      },
      {
        onSuccess: (visit) => {
          router.push(`/emergency/${visit.id}`);
        },
      }
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/emergency"
          className="rounded-md p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("registerVisit")}</h1>
          <p className="text-sm text-muted-foreground">{t("registerSubtitle")}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          {/* Patient ID */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("patientId")} *</label>
            <input
              type="text"
              {...register("patient_id")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("enterPatientId")}
            />
            {errors.patient_id && (
              <p className="mt-1 text-xs text-red-600">{errors.patient_id.message}</p>
            )}
          </div>

          {/* Arrival Mode */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("arrivalMode")}</label>
            <select
              {...register("arrival_mode")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            >
              {arrivalModes.map((m) => (
                <option key={m} value={m}>
                  {t(`mode.${m}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Brought By */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("broughtBy")}</label>
            <input
              type="text"
              {...register("brought_by")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("broughtByPlaceholder")}
            />
          </div>

          {/* Chief Complaint */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("chiefComplaint")} *</label>
            <textarea
              {...register("chief_complaint")}
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("complaintPlaceholder")}
            />
            {errors.chief_complaint && (
              <p className="mt-1 text-xs text-red-600">{errors.chief_complaint.message}</p>
            )}
          </div>

          {/* Trauma Flag */}
          <div className="mb-4 flex items-center gap-2">
            <input
              type="checkbox"
              id="is_trauma"
              {...register("is_trauma")}
              className="h-4 w-4 rounded border-input"
            />
            <label htmlFor="is_trauma" className="flex items-center gap-1 text-sm font-medium text-red-600">
              <Siren className="h-4 w-4" /> {t("traumaCase")}
            </label>
          </div>

          {/* Allergies */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("allergies")}</label>
            <input
              type="text"
              {...register("allergies_noted")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("allergiesPlaceholder")}
            />
          </div>

          {/* Notes */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("notes")}</label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
          </div>
        </div>

        {/* Submit */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={registerMutation.isPending || !isValid}
            className="rounded-md bg-red-600 px-6 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {registerMutation.isPending ? t("saving") : t("registerVisit")}
          </button>
          <Link
            href="/emergency"
            className="rounded-md border border-input px-6 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            {t("cancel")}
          </Link>
        </div>
      </form>
    </div>
  );
}
