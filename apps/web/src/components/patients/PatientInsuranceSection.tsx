"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Shield, Plus, Star, Edit2, Trash2, X, Check } from "lucide-react";
import type {
  PatientInsuranceCreate,
  PatientInsuranceResponse,
  PatientInsuranceUpdate,
} from "@aifya/shared";
import {
  usePatientInsurances,
  useAddPatientInsurance,
  useUpdatePatientInsurance,
  useDeletePatientInsurance,
  useSetPrimaryPatientInsurance,
  useInsuranceSchemes,
} from "@/hooks/useInsurance";
import { formatDate } from "@/lib/utils";

/**
 * Multi-insurance management section for the patient detail page.
 * Supports SHA + private + corporate insurers per audit 2026-05-14.
 *
 * @param props.patientId - Patient UUID
 * @returns Insurance section with list, add, edit, delete, set-primary
 */
export function PatientInsuranceSection({
  patientId,
}: {
  patientId: string;
}) {
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const { data, isLoading } = usePatientInsurances(patientId);
  const { data: schemes } = useInsuranceSchemes();
  const addMutation = useAddPatientInsurance(patientId);
  const updateMutation = useUpdatePatientInsurance(patientId);
  const deleteMutation = useDeletePatientInsurance(patientId);
  const setPrimaryMutation = useSetPrimaryPatientInsurance(patientId);

  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const items = data?.items ?? [];
  const schemeOptions = schemes?.items ?? [];

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-foreground">
          <Shield className="h-5 w-5" />
          <h2 className="font-semibold">{t("insurancePolicies")}</h2>
        </div>
        <button
          type="button"
          onClick={() => {
            setIsAdding(true);
            setEditingId(null);
          }}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          aria-label={t("addInsurance")}
        >
          <Plus className="h-3.5 w-3.5" />
          {t("addInsurance")}
        </button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">{tc("loading")}</p>
      ) : items.length === 0 && !isAdding ? (
        <p className="text-sm text-muted-foreground">{t("noInsurance")}</p>
      ) : null}

      <ul className="space-y-3">
        {items.map((entry) =>
          editingId === entry.id ? (
            <li key={entry.id}>
              <InsuranceForm
                initial={entry}
                schemes={schemeOptions}
                onCancel={() => setEditingId(null)}
                onSubmit={async (data) => {
                  await updateMutation.mutateAsync({
                    insuranceId: entry.id,
                    data,
                  });
                  setEditingId(null);
                }}
                isPending={updateMutation.isPending}
              />
            </li>
          ) : (
            <InsuranceRow
              key={entry.id}
              entry={entry}
              onEdit={() => {
                setEditingId(entry.id);
                setIsAdding(false);
              }}
              onSetPrimary={() =>
                setPrimaryMutation.mutate({ insuranceId: entry.id })
              }
              onDelete={() => {
                if (window.confirm(t("confirmRemoveInsurance"))) {
                  deleteMutation.mutate({ insuranceId: entry.id });
                }
              }}
            />
          ),
        )}

        {isAdding ? (
          <li>
            <InsuranceForm
              schemes={schemeOptions}
              onCancel={() => setIsAdding(false)}
              onSubmit={async (data) => {
                await addMutation.mutateAsync(data as PatientInsuranceCreate);
                setIsAdding(false);
              }}
              isPending={addMutation.isPending}
            />
          </li>
        ) : null}
      </ul>
    </section>
  );
}

function InsuranceRow({
  entry,
  onEdit,
  onSetPrimary,
  onDelete,
}: {
  entry: PatientInsuranceResponse;
  onEdit: () => void;
  onSetPrimary: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("patients");
  return (
    <li
      className={`rounded-lg border p-3 transition-colors dark:border-border ${
        entry.is_primary
          ? "border-primary/40 bg-primary/5 dark:border-primary/40 dark:bg-primary/10"
          : "border-border bg-background"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">
              {entry.scheme_name ?? "—"}
            </span>
            {entry.scheme_type ? (
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                {entry.scheme_type}
              </span>
            ) : null}
            {entry.is_primary ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold uppercase text-primary-foreground">
                <Star className="h-3 w-3" />
                {t("primary")}
              </span>
            ) : null}
            {!entry.is_active ? (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                {t("inactive")}
              </span>
            ) : null}
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {entry.member_number}
          </p>
          {entry.principal_name ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("principalName")}: {entry.principal_name}
              {entry.relationship ? ` (${entry.relationship})` : ""}
            </p>
          ) : null}
          {entry.valid_to ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("validTo")}: {formatDate(entry.valid_to)}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!entry.is_primary ? (
            <button
              type="button"
              onClick={onSetPrimary}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label={t("setAsPrimary")}
              title={t("setAsPrimary")}
            >
              <Star className="h-4 w-4" />
            </button>
          ) : null}
          <button
            type="button"
            onClick={onEdit}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Edit"
          >
            <Edit2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            aria-label="Remove"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </li>
  );
}

interface SchemeOption {
  id: string;
  name: string;
  scheme_type: string;
}

function InsuranceForm({
  initial,
  schemes,
  onCancel,
  onSubmit,
  isPending,
}: {
  initial?: PatientInsuranceResponse;
  schemes: SchemeOption[];
  onCancel: () => void;
  onSubmit: (data: PatientInsuranceUpdate) => Promise<void> | void;
  isPending: boolean;
}) {
  const t = useTranslations("patients");
  const tc = useTranslations("common");

  const [schemeId, setSchemeId] = useState<string>(
    initial?.scheme_id ?? schemes[0]?.id ?? "",
  );
  const [memberNumber, setMemberNumber] = useState<string>(
    initial?.member_number ?? "",
  );
  const [principalName, setPrincipalName] = useState<string>(
    initial?.principal_name ?? "",
  );
  const [relationship, setRelationship] = useState<string>(
    initial?.relationship ?? "self",
  );
  const [validTo, setValidTo] = useState<string>(
    initial?.valid_to ? initial.valid_to.slice(0, 10) : "",
  );
  const [isPrimary, setIsPrimary] = useState<boolean>(
    initial?.is_primary ?? false,
  );
  const [notes, setNotes] = useState<string>(initial?.notes ?? "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!schemeId || !memberNumber) return;
    await onSubmit({
      scheme_id: schemeId,
      member_number: memberNumber,
      principal_name: principalName || null,
      relationship: (relationship || null) as PatientInsuranceUpdate["relationship"],
      valid_to: validTo ? new Date(validTo).toISOString() : null,
      is_primary: isPrimary,
      notes: notes || null,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-3 dark:bg-primary/10"
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-foreground">
            {t("scheme")} *
          </label>
          <select
            value={schemeId}
            onChange={(e) => setSchemeId(e.target.value)}
            required
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">—</option>
            {schemes.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.scheme_type})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-foreground">
            {t("memberNumber")} *
          </label>
          <input
            type="text"
            value={memberNumber}
            onChange={(e) => setMemberNumber(e.target.value)}
            required
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-foreground">
            {t("principalName")}
          </label>
          <input
            type="text"
            value={principalName}
            onChange={(e) => setPrincipalName(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-foreground">
            {t("relationship")}
          </label>
          <select
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="self">{t("selfRel")}</option>
            <option value="spouse">{t("spouse")}</option>
            <option value="child">{t("child")}</option>
            <option value="parent">{t("parent")}</option>
            <option value="other">{t("other")}</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-foreground">
            {t("validTo")}
          </label>
          <input
            type="date"
            value={validTo}
            onChange={(e) => setValidTo(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="flex items-end">
          <label className="inline-flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={isPrimary}
              onChange={(e) => setIsPrimary(e.target.checked)}
              className="rounded border-input"
            />
            {t("primary")}
          </label>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-foreground">
          {t("notes")}
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
        >
          <X className="h-3.5 w-3.5" />
          {tc("cancel")}
        </button>
        <button
          type="submit"
          disabled={isPending || !schemeId || !memberNumber}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check className="h-3.5 w-3.5" />
          {tc("save")}
        </button>
      </div>
    </form>
  );
}
