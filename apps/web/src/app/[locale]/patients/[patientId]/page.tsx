"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, User, Phone, MapPin, Heart, Edit } from "lucide-react";
import { Link } from "@/i18n/routing";
import { usePatient } from "@/hooks/usePatients";
import { useAuth } from "@/components/providers/AuthProvider";
import { formatDate } from "@/lib/utils";
import { PatientTimeline } from "@/components/patients/PatientTimeline";
import { PatientInsuranceSection } from "@/components/patients/PatientInsuranceSection";

/** Roles permitted to edit patient records (must mirror backend RBAC). */
const PATIENT_EDIT_ROLES = ["admin", "facility_admin", "records_admin"] as const;

/**
 * Patient detail page with demographics, contact, insurance, and timeline.
 * @returns Patient detail view
 */
export default function PatientDetailPage() {
  const params = useParams<{ patientId: string }>();
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const { data: patient, isLoading } = usePatient(params.patientId);
  const { user } = useAuth();
  const canEdit =
    !!user &&
    user.roles.some((r) =>
      (PATIENT_EDIT_ROLES as readonly string[]).includes(r),
    );

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">{t("patientNotFound")}</p>
        <Link
          href="/patients"
          className="text-sm text-primary hover:underline dark:text-primary"
        >
          {tc("back")}
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <Link
          href="/patients"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {patient.first_name} {patient.middle_name ?? ""} {patient.last_name}
          </h1>
          <p className="font-mono text-sm text-muted-foreground">
            {patient.mrn}
          </p>
        </div>
        {canEdit ? (
          <Link
            href={`/patients/${params.patientId}/edit`}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            aria-label={t("editPatient")}
          >
            <Edit className="h-4 w-4" />
            {t("editPatient")}
          </Link>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Demographics */}
        <InfoCard
          title={t("demographics")}
          icon={<User className="h-5 w-5" />}
        >
          <InfoRow label={t("dateOfBirth")} value={formatDate(patient.date_of_birth)} />
          <InfoRow label={t("gender")} value={patient.gender} capitalize />
          <InfoRow label={t("nationalId")} value={patient.national_id} />
          <InfoRow label={t("maritalStatus")} value={patient.marital_status} capitalize />
          <InfoRow label={t("occupation")} value={patient.occupation} />
        </InfoCard>

        {/* Contact */}
        <InfoCard
          title={t("contactInfo")}
          icon={<Phone className="h-5 w-5" />}
        >
          <InfoRow label={t("phoneNumber")} value={patient.phone_number} />
          <InfoRow label={t("alternatePhone")} value={patient.alternate_phone} />
          <InfoRow label={t("email")} value={patient.email} />
        </InfoCard>

        {/* Address */}
        <InfoCard title={t("address")} icon={<MapPin className="h-5 w-5" />}>
          <InfoRow label={t("county")} value={patient.county} />
          <InfoRow label={t("subCounty")} value={patient.sub_county} />
          <InfoRow label={t("ward")} value={patient.ward} />
          <InfoRow label={t("village")} value={patient.village} />
          <InfoRow label={t("postalAddress")} value={patient.postal_address} />
        </InfoCard>

        {/* Medical Info */}
        <InfoCard
          title={t("medicalInfo")}
          icon={<Heart className="h-5 w-5" />}
        >
          <InfoRow label={t("bloodGroup")} value={patient.blood_group} />
          <InfoRow
            label={t("allergies")}
            value={patient.allergies?.join(", ") ?? null}
          />
          <InfoRow
            label={t("chronicConditions")}
            value={patient.chronic_conditions?.join(", ") ?? null}
          />
        </InfoCard>

        {/* Next of Kin */}
        <InfoCard title={t("nextOfKin")} icon={<User className="h-5 w-5" />}>
          <InfoRow label={t("nextOfKinName")} value={patient.next_of_kin_name} />
          <InfoRow label={t("nextOfKinPhone")} value={patient.next_of_kin_phone} />
          <InfoRow
            label={t("nextOfKinRelationship")}
            value={patient.next_of_kin_relationship}
          />
        </InfoCard>
      </div>

      {/* Multi-insurance section (audit 2026-05-14) */}
      <section className="mt-8">
        <PatientInsuranceSection patientId={params.patientId} />
      </section>

      {/* Timeline */}
      <section className="mt-8">
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          {t("timeline")}
        </h2>
        <PatientTimeline patientId={params.patientId} />
      </section>
    </div>
  );
}

function InfoCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center gap-2 text-foreground">
        {icon}
        <h2 className="font-semibold">{title}</h2>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  capitalize,
}: {
  label: string;
  value: string | null | undefined;
  capitalize?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={`font-medium text-foreground ${
          capitalize ? "capitalize" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}
