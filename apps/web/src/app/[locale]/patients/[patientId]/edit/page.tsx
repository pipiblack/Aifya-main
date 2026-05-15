"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import {
  patientUpdateSchema,
  type PatientUpdateFormData,
} from "@/lib/validations/patient";
import { usePatient, useUpdatePatient } from "@/hooks/usePatients";
import { useAuth } from "@/components/providers/AuthProvider";
import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";

/** Roles permitted to edit patient records — mirrors backend RBAC. */
const PATIENT_EDIT_ROLES = [
  "admin",
  "facility_admin",
  "records_admin",
] as const;

/**
 * Patient edit page. Restricted to admin-level roles per audit 2026-05-14.
 * Non-admins see a permission-denied notice. The backend enforces the same
 * RBAC; this gate just prevents the form from rendering.
 *
 * Insurance is managed via the dedicated multi-insurance section on the
 * detail page, not here.
 *
 * @returns Edit form page
 */
export default function PatientEditPage() {
  const params = useParams<{ patientId: string }>();
  const router = useRouter();
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const { user, isLoading: authLoading } = useAuth();
  const { data: patient, isLoading } = usePatient(params.patientId);
  const updateMutation = useUpdatePatient(params.patientId);

  const canEdit =
    !!user &&
    user.roles.some((r) =>
      (PATIENT_EDIT_ROLES as readonly string[]).includes(r),
    );

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PatientUpdateFormData>({
    resolver: zodResolver(patientUpdateSchema),
  });

  // Hydrate form once the patient loads.
  useEffect(() => {
    if (!patient) return;
    reset({
      first_name: patient.first_name,
      middle_name: patient.middle_name ?? "",
      last_name: patient.last_name,
      date_of_birth:
        typeof patient.date_of_birth === "string"
          ? patient.date_of_birth.slice(0, 10)
          : "",
      gender: patient.gender as PatientUpdateFormData["gender"],
      national_id: patient.national_id ?? "",
      passport_number: patient.passport_number ?? "",
      phone_number: patient.phone_number,
      alternate_phone: patient.alternate_phone ?? "",
      email: patient.email ?? "",
      county: patient.county ?? "",
      sub_county: patient.sub_county ?? "",
      ward: patient.ward ?? "",
      village: patient.village ?? "",
      postal_address: patient.postal_address ?? "",
      occupation: patient.occupation ?? "",
      marital_status: (patient.marital_status as PatientUpdateFormData["marital_status"]) ?? null,
      next_of_kin_name: patient.next_of_kin_name ?? "",
      next_of_kin_phone: patient.next_of_kin_phone ?? "",
      next_of_kin_relationship: patient.next_of_kin_relationship ?? "",
      sha_number: patient.sha_number ?? "",
      blood_group: patient.blood_group ?? "",
    });
  }, [patient, reset]);

  const onSubmit = async (data: PatientUpdateFormData) => {
    // Strip empty strings → null so backend regex/optional validators behave.
    const cleaned: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      cleaned[key] = value === "" ? null : value;
    }
    try {
      await updateMutation.mutateAsync(cleaned);
      router.push(`/patients/${params.patientId}`);
    } catch {
      // Surfaced via mutation state below
    }
  };

  if (authLoading || isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  if (!canEdit) {
    return (
      <div className="mx-auto max-w-2xl p-6 lg:p-8">
        <Link
          href={`/patients/${params.patientId}`}
          className="mb-4 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{t("editRestricted")}</p>
        </div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">{t("patientNotFound")}</p>
        <Link
          href="/patients"
          className="text-sm text-primary hover:underline"
        >
          {tc("back")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      <div className="mb-6 flex items-center gap-4">
        <Link
          href={`/patients/${params.patientId}`}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t("editPatient")}
          </h1>
          <p className="font-mono text-sm text-muted-foreground">
            {patient.mrn} · {patient.first_name} {patient.last_name}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        {/* Demographics */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("demographics")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label={t("firstName")} error={errors.first_name?.message}>
              <input
                {...register("first_name")}
                className={inputClass(!!errors.first_name)}
              />
            </FormField>
            <FormField label={t("middleName")} error={errors.middle_name?.message}>
              <input {...register("middle_name")} className={inputClass(false)} />
            </FormField>
            <FormField label={t("lastName")} error={errors.last_name?.message}>
              <input
                {...register("last_name")}
                className={inputClass(!!errors.last_name)}
              />
            </FormField>
            <FormField
              label={t("dateOfBirth")}
              error={errors.date_of_birth?.message}
            >
              <input
                type="date"
                {...register("date_of_birth")}
                className={inputClass(!!errors.date_of_birth)}
              />
            </FormField>
            <FormField label={t("gender")} error={errors.gender?.message}>
              <select {...register("gender")} className={inputClass(false)}>
                <option value="male">{t("male") || "Male"}</option>
                <option value="female">{t("female") || "Female"}</option>
                <option value="other">{t("other") || "Other"}</option>
              </select>
            </FormField>
            <FormField label={t("nationalId")} error={errors.national_id?.message}>
              <input
                {...register("national_id")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("maritalStatus")}
              error={errors.marital_status?.message}
            >
              <select
                {...register("marital_status")}
                className={inputClass(false)}
              >
                <option value="">—</option>
                <option value="single">{t("single")}</option>
                <option value="married">{t("married")}</option>
                <option value="divorced">{t("divorced")}</option>
                <option value="widowed">{t("widowed")}</option>
              </select>
            </FormField>
            <FormField label={t("occupation")} error={errors.occupation?.message}>
              <input
                {...register("occupation")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Contact */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("contactInfo")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("phoneNumber")}
              error={errors.phone_number?.message}
            >
              <input
                {...register("phone_number")}
                className={inputClass(!!errors.phone_number)}
              />
            </FormField>
            <FormField
              label={t("alternatePhone")}
              error={errors.alternate_phone?.message}
            >
              <input
                {...register("alternate_phone")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField label={t("email")} error={errors.email?.message}>
              <input
                type="email"
                {...register("email")}
                className={inputClass(!!errors.email)}
              />
            </FormField>
          </div>
        </section>

        {/* Address */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("address")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label={t("county")} error={errors.county?.message}>
              <input {...register("county")} className={inputClass(false)} />
            </FormField>
            <FormField label={t("subCounty")} error={errors.sub_county?.message}>
              <input
                {...register("sub_county")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField label={t("ward")} error={errors.ward?.message}>
              <input {...register("ward")} className={inputClass(false)} />
            </FormField>
            <FormField label={t("village")} error={errors.village?.message}>
              <input {...register("village")} className={inputClass(false)} />
            </FormField>
            <FormField
              label={t("postalAddress")}
              error={errors.postal_address?.message}
            >
              <input
                {...register("postal_address")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Next of Kin */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("nextOfKin")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("nextOfKinName")}
              error={errors.next_of_kin_name?.message}
            >
              <input
                {...register("next_of_kin_name")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("nextOfKinPhone")}
              error={errors.next_of_kin_phone?.message}
            >
              <input
                {...register("next_of_kin_phone")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("nextOfKinRelationship")}
              error={errors.next_of_kin_relationship?.message}
            >
              <input
                {...register("next_of_kin_relationship")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Medical */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("medicalInfo")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label={t("shaNumber")} error={errors.sha_number?.message}>
              <input
                {...register("sha_number")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("bloodGroup")}
              error={errors.blood_group?.message}
            >
              <select
                {...register("blood_group")}
                className={inputClass(!!errors.blood_group)}
              >
                <option value="">—</option>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((bg) => (
                  <option key={bg} value={bg}>
                    {bg}
                  </option>
                ))}
              </select>
            </FormField>
          </div>
        </section>

        {updateMutation.isError ? (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {t("updateError")}
          </div>
        ) : null}

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={isSubmitting || updateMutation.isPending}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            {updateMutation.isPending ? tc("loading") : t("saveChanges")}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground shadow-sm hover:bg-accent"
          >
            {tc("cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}

function inputClass(hasError: boolean): string {
  return cn(
    "w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-ring",
    hasError ? "border-destructive focus:ring-destructive" : "border-input",
  );
}

function FormField({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
