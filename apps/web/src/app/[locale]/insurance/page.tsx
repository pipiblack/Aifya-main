"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  DollarSign,
  ExternalLink,
  FileText,
  RefreshCw,
  Send,
  Shield,
  XCircle,
} from "lucide-react";
import {
  useInsuranceSummary,
  useInsuranceClaims,
  useInsuranceSchemes,
  useSubmitClaimToClaimFlow,
  useSyncClaimWithClaimFlow,
} from "@/hooks/useInsurance";
import { cn } from "@/lib/utils";

const CLAIM_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  processing: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  approved: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  partially_approved:
    "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  rejected: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  paid: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
};

const CLAIMFLOW_API_URL =
  process.env.NEXT_PUBLIC_CLAIMFLOW_URL ?? "http://localhost:8080";

function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2 })}`;
}

/** Extract ClaimFlow external id from sha_reference ("CF:<id>"). */
function extractCfId(ref: string | null | undefined): string | null {
  if (!ref) return null;
  return ref.startsWith("CF:") ? ref.slice(3) : null;
}

interface ClaimRowProps {
  claim: {
    id: string;
    claim_number: string;
    patient_name: string | null;
    scheme_name: string | null;
    member_number: string;
    claim_amount: number;
    claim_date: string;
    status: string;
    sha_reference?: string | null;
  };
  onAction: (msg: string | null) => void;
}

/** One row of the claim table with ClaimFlow action buttons. */
function ClaimRow({ claim, onAction }: ClaimRowProps) {
  const t = useTranslations("insurance");
  const submit = useSubmitClaimToClaimFlow(claim.id);
  const sync = useSyncClaimWithClaimFlow(claim.id);
  const externalId = extractCfId(claim.sha_reference);
  const cfStatus = externalId ? t("claimFlow.inFlow") || "in claimflow" : null;

  const handleSubmit = async () => {
    onAction(null);
    try {
      const result = await submit.mutateAsync();
      onAction(
        `Submitted. ClaimFlow status: ${result.claimflow_status ?? "submitted"}`,
      );
    } catch (e: unknown) {
      onAction(e instanceof Error ? e.message : String(e));
    }
  };
  const handleSync = async () => {
    onAction(null);
    try {
      const result = await sync.mutateAsync();
      onAction(`Synced. ClaimFlow status: ${result.claimflow_status ?? "—"}`);
    } catch (e: unknown) {
      onAction(e instanceof Error ? e.message : String(e));
    }
  };

  const canSubmit = !externalId && ["draft", "pending"].includes(claim.status);
  const canSync = !!externalId;
  const viewUrl = externalId
    ? `${CLAIMFLOW_API_URL.replace(/\/$/, "")}/claims/${externalId}`
    : null;

  return (
    <tr className="bg-card hover:bg-muted/50">
      <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
        {claim.claim_number}
      </td>
      <td className="px-4 py-3 font-medium text-foreground">
        {claim.patient_name || "—"}
      </td>
      <td className="px-4 py-3 text-muted-foreground">
        {claim.scheme_name || "—"}
      </td>
      <td className="px-4 py-3 text-muted-foreground">{claim.member_number}</td>
      <td className="px-4 py-3 font-medium">{formatKES(claim.claim_amount)}</td>
      <td className="px-4 py-3 text-muted-foreground">
        {new Date(claim.claim_date).toLocaleDateString()}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              CLAIM_STYLES[claim.status] ?? CLAIM_STYLES.draft,
            )}
          >
            {t("claimStatusLabel") || "Local"}:{" "}
            {t(`claimStatus.${claim.status}`)}
          </span>
          {cfStatus && (
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
              ClaimFlow: {externalId?.slice(0, 8)}…
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-1">
          {canSubmit && (
            <button
              type="button"
              disabled={submit.isPending}
              onClick={handleSubmit}
              className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900 disabled:opacity-60"
              title="Submit to ClaimFlow"
            >
              <Send className="h-3 w-3" />
              {t("submitToClaimFlow") || "Submit to ClaimFlow"}
            </button>
          )}
          {canSync && (
            <button
              type="button"
              disabled={sync.isPending}
              onClick={handleSync}
              className="inline-flex items-center gap-1 rounded-lg border border-purple-200 bg-purple-50 px-2 py-1 text-xs font-medium text-purple-700 hover:bg-purple-100 dark:border-purple-900 dark:bg-purple-950 dark:text-purple-300 dark:hover:bg-purple-900 disabled:opacity-60"
              title="Sync status from ClaimFlow"
            >
              <RefreshCw className="h-3 w-3" />
              {t("syncStatus") || "Sync"}
            </button>
          )}
          {viewUrl && (
            <a
              href={viewUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
              title="Open in ClaimFlow"
            >
              <ExternalLink className="h-3 w-3" />
              {t("viewInClaimFlow") || "View"}
            </a>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function InsurancePage() {
  const t = useTranslations("insurance");
  const [tab, setTab] = useState<"claims" | "schemes">("claims");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const { data: summary, isLoading: summaryLoading } = useInsuranceSummary();
  const { data: claims, isLoading: claimsLoading } = useInsuranceClaims();
  const { data: schemes } = useInsuranceSchemes();

  const summaryCards = [
    {
      label: t("totalClaims"),
      value: summary?.total_claims ?? 0,
      icon: FileText,
      color: "text-blue-600 dark:text-blue-400",
    },
    {
      label: t("pendingClaims"),
      value: summary?.pending_claims ?? 0,
      icon: Clock,
      color: "text-amber-600 dark:text-amber-400",
    },
    {
      label: t("submittedClaims"),
      value: summary?.submitted_claims ?? 0,
      icon: Send,
      color: "text-indigo-600 dark:text-indigo-400",
    },
    {
      label: t("approvedClaims"),
      value: summary?.approved_claims ?? 0,
      icon: CheckCircle,
      color: "text-green-600 dark:text-green-400",
    },
    {
      label: t("rejectedClaims"),
      value: summary?.rejected_claims ?? 0,
      icon: XCircle,
      color: "text-red-600 dark:text-red-400",
    },
    {
      label: t("totalClaimValue"),
      value: summary ? formatKES(summary.total_claim_value) : "—",
      icon: DollarSign,
      color: "text-purple-600 dark:text-purple-400",
    },
    {
      label: t("activeSchemes"),
      value: summary?.active_schemes ?? 0,
      icon: Shield,
      color: "text-cyan-600 dark:text-cyan-400",
    },
    {
      label: t("preAuthPending"),
      value: summary?.preauth_pending ?? 0,
      icon: AlertTriangle,
      color: "text-orange-600 dark:text-orange-400",
    },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]"
          >
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">
                {card.label}
              </span>
            </div>
            <p className="mt-1 text-lg font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="flex gap-2 border-b border-border">
        {(["claims", "schemes"] as const).map((t_) => (
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

      {actionMessage && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200">
          {actionMessage}
        </div>
      )}

      {tab === "claims" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("claimNumber")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("scheme")}</th>
                <th className="px-4 py-3">{t("memberNumber")}</th>
                <th className="px-4 py-3">{t("amount")}</th>
                <th className="px-4 py-3">{t("date")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
                <th className="px-4 py-3">{t("claimFlowActions") || "ClaimFlow"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {claimsLoading ? (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-8 text-center text-muted-foreground/70"
                  >
                    {t("loading")}
                  </td>
                </tr>
              ) : !claims?.items.length ? (
                <tr>
                  <td
                    colSpan={8}
                    className="px-4 py-8 text-center text-muted-foreground/70"
                  >
                    {t("noClaims")}
                  </td>
                </tr>
              ) : (
                claims.items.map((c) => (
                  <ClaimRow key={c.id} claim={c} onAction={setActionMessage} />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "schemes" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schemes?.items.map((s) => (
            <div
              key={s.id}
              className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">{s.name}</h3>
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                  {t(`schemeType.${s.scheme_type}`)}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {s.scheme_code}
              </p>
              {s.contact_person && (
                <p className="text-xs text-muted-foreground/70">
                  {s.contact_person} — {s.phone}
                </p>
              )}
            </div>
          ))}
          {!schemes?.items.length && (
            <p className="col-span-full py-8 text-center text-muted-foreground/70">
              {t("noSchemes")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
