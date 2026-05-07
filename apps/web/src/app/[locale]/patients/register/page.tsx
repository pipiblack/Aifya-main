"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import {
  patientCreateSchema,
  type PatientCreateFormData,
} from "@/lib/validations/patient";
import { useRegisterPatient } from "@/hooks/usePatients";
import { HelpTooltip } from "@/components/help/HelpTooltip";
import { cn } from "@/lib/utils";

/**
 * Patient Registration form page.
 * Supports offline submission — mutations queue to IndexedDB when offline.
 * All strings internationalized via next-intl.
 * @returns Registration form page
 */
export default function PatientRegistrationPage() {
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const router = useRouter();
  const registerMutation = useRegisterPatient();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PatientCreateFormData>({
    resolver: zodResolver(patientCreateSchema),
    defaultValues: {
      gender: "male",
    },
  });

  const onSubmit = async (data: PatientCreateFormData) => {
    try {
      const patient = await registerMutation.mutateAsync(data);
      router.push(`/patients/${patient.id}`);
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      <h1 className="mb-6 text-2xl font-bold text-foreground">
        {t("register")}
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        {/* Demographics */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("demographics")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("firstName")}
              error={errors.first_name?.message}
              required
            >
              <input
                {...register("first_name")}
                className={inputClass(!!errors.first_name)}
              />
            </FormField>
            <FormField
              label={t("middleName")}
              error={errors.middle_name?.message}
            >
              <input
                {...register("middle_name")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("lastName")}
              error={errors.last_name?.message}
              required
            >
              <input
                {...register("last_name")}
                className={inputClass(!!errors.last_name)}
              />
            </FormField>
            <FormField
              label={t("dateOfBirth")}
              error={errors.date_of_birth?.message}
              required
            >
              <input
                type="date"
                {...register("date_of_birth")}
                className={inputClass(!!errors.date_of_birth)}
              />
            </FormField>
            <FormField
              label={t("gender")}
              error={errors.gender?.message}
              required
            >
              <select
                {...register("gender")}
                className={inputClass(!!errors.gender)}
              >
                <option value="male">{t("male")}</option>
                <option value="female">{t("female")}</option>
                <option value="other">{t("other")}</option>
              </select>
            </FormField>
            <FormField
              label={t("nationalId")}
              error={errors.national_id?.message}
              help={t("help.nationalId")}
            >
              <input
                {...register("national_id")}
                placeholder="12345678"
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Contact Information */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("contactInfo")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("phoneNumber")}
              error={errors.phone_number?.message}
              required
              help={t("help.phoneNumber")}
            >
              <input
                type="tel"
                {...register("phone_number")}
                placeholder="0712345678"
                className={inputClass(!!errors.phone_number)}
              />
            </FormField>
            <FormField
              label={t("alternatePhone")}
              error={errors.alternate_phone?.message}
            >
              <input
                type="tel"
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
            <FormField
              label={t("subCounty")}
              error={errors.sub_county?.message}
            >
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
                type="tel"
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

        {/* Insurance */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("insurance")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("shaNumber")}
              error={errors.sha_number?.message}
            >
              <input
                {...register("sha_number")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("insuranceProvider")}
              error={errors.insurance_provider?.message}
            >
              <input
                {...register("insurance_provider")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("insuranceMemberNumber")}
              error={errors.insurance_member_number?.message}
            >
              <input
                {...register("insurance_member_number")}
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
            <FormField
              label={t("bloodGroup")}
              error={errors.blood_group?.message}
            >
              <select
                {...register("blood_group")}
                className={inputClass(false)}
              >
                <option value="">—</option>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(
                  (bg) => (
                    <option key={bg} value={bg}>
                      {bg}
                    </option>
                  )
                )}
              </select>
            </FormField>
          </div>
        </section>

        {/* Error display */}
        {registerMutation.isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {t("registrationError")}
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={isSubmitting || registerMutation.isPending}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            {registerMutation.isPending ? tc("loading") : t("register")}
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
    hasError
      ? "border-destructive focus:ring-destructive"
      : "border-input"
  );
}

function FormField({
  label,
  error,
  required,
  help,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  /** Optional contextual help shown via a `?` tooltip next to the label. */
  help?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground inline-flex items-center">
        {label}
        {required && <span className="ml-1 text-destructive">*</span>}
        {help && <HelpTooltip content={help} />}
      </label>
      {children}
      {error && (
        <p className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
