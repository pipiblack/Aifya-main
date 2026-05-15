"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/routing";
import { useTranslations } from "next-intl";
import { CheckCircle, FileText, Ban, Wallet } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatKES } from "@/lib/utils";
import {
  useSupplierInvoice,
  useApproveSupplierInvoice,
  usePaySupplierInvoice,
  useCancelSupplierInvoice,
} from "@/hooks/useSuppliers";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  received: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  approved: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  paid: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  cancelled: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

/**
 * Supplier invoice detail page with approve / pay / cancel actions.
 *
 * Roles are enforced server-side (finance_admin for approve/pay); the UI shows
 * buttons opportunistically — server will return 403 if the user is not
 * authorised.
 *
 * @returns Supplier invoice detail page
 */
export default function SupplierInvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const router = useRouter();
  const t = useTranslations("billing");
  const tc = useTranslations("common");

  const { data: invoice, isLoading } = useSupplierInvoice(id);
  const approve = useApproveSupplierInvoice(id);
  const pay = usePaySupplierInvoice(id);
  const cancel = useCancelSupplierInvoice(id);

  const [payAmount, setPayAmount] = useState<number>(0);
  const [payMethod, setPayMethod] = useState<
    "bank" | "cash" | "mpesa" | "cheque"
  >("bank");
  const [payReference, setPayReference] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  if (isLoading) return <PageSkeleton />;
  if (!invoice) {
    return (
      <div className="p-6 lg:p-8">
        <EmptyState
          icon={FileText}
          title={t("supplierInvoiceNotFound") || "Supplier invoice not found"}
        />
      </div>
    );
  }

  const runAction = async (fn: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await fn();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setActionError(msg);
    }
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={FileText}
        title={invoice.our_reference}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          {
            label: t("supplierInvoices") || "Supplier invoices",
            href: "/billing/supplier-invoices",
          },
          { label: invoice.our_reference },
        ]}
        actions={
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              STATUS_BADGE[invoice.status] ?? STATUS_BADGE.draft
            }`}
          >
            {invoice.status}
          </span>
        }
      />

      {/* Header info */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <div className="text-xs uppercase text-muted-foreground">
            {t("supplier") || "Supplier"}
          </div>
          <Link
            href={`/billing/suppliers/${invoice.supplier_id}`}
            className="mt-1 block text-sm font-semibold text-blue-600 hover:underline dark:text-blue-400"
          >
            {invoice.supplier_name ?? "—"}
          </Link>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <div className="text-xs uppercase text-muted-foreground">
            {t("invoiceNumber") || "Invoice #"}
          </div>
          <div className="mt-1 font-mono text-sm">{invoice.invoice_number}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <div className="text-xs uppercase text-muted-foreground">
            {t("invoiceDate") || "Invoice date"}
          </div>
          <div className="mt-1 text-sm">
            {new Date(invoice.invoice_date).toLocaleDateString()}
            {invoice.due_date && (
              <span className="ml-2 text-xs text-muted-foreground">
                {t("dueOn") || "due"}{" "}
                {new Date(invoice.due_date).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Lines */}
      <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">{t("description") || "Description"}</th>
              <th className="px-4 py-3 w-24">{t("quantity") || "Qty"}</th>
              <th className="px-4 py-3 w-40">{t("unitPrice") || "Unit"}</th>
              <th className="px-4 py-3 w-32">{t("account") || "Account"}</th>
              <th className="px-4 py-3 w-32 text-right">{t("total") || "Total"}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {invoice.lines.map((line) => (
              <tr key={line.id ?? line.description}>
                <td className="px-4 py-3">{line.description}</td>
                <td className="px-4 py-3">{line.quantity}</td>
                <td className="px-4 py-3">{formatKES(line.unit_price)}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {line.account_code}
                </td>
                <td className="px-4 py-3 text-right font-medium">
                  {formatKES(line.line_total ?? line.quantity * line.unit_price)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Totals */}
      <div className="flex justify-end">
        <div className="rounded-xl border border-border bg-card p-4 text-sm shadow-[var(--shadow-card)]">
          <div className="flex justify-between gap-8">
            <span className="text-muted-foreground">{t("subtotal")}</span>
            <span className="font-medium">{formatKES(invoice.subtotal)}</span>
          </div>
          <div className="flex justify-between gap-8">
            <span className="text-muted-foreground">VAT</span>
            <span className="font-medium">{formatKES(invoice.vat_amount)}</span>
          </div>
          <div className="flex justify-between gap-8">
            <span className="text-muted-foreground">WHT</span>
            <span className="font-medium">- {formatKES(invoice.wht_amount)}</span>
          </div>
          <div className="mt-2 flex justify-between gap-8 border-t border-border pt-2 text-base">
            <span className="font-semibold">{t("total") || "Total"}</span>
            <span className="font-bold text-foreground">
              {formatKES(invoice.total)}
            </span>
          </div>
          <div className="flex justify-between gap-8 text-xs text-muted-foreground">
            <span>{t("paid") || "Paid"}</span>
            <span>{formatKES(invoice.paid_amount)}</span>
          </div>
          {invoice.balance > 0 && (
            <div className="flex justify-between gap-8 font-medium text-amber-600 dark:text-amber-400">
              <span>{t("balance") || "Balance"}</span>
              <span>{formatKES(invoice.balance)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        {invoice.status === "draft" && (
          <>
            <button
              type="button"
              disabled={approve.isPending}
              onClick={() => runAction(() => approve.mutateAsync())}
              className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-60"
            >
              <CheckCircle className="h-4 w-4" />
              {t("approve") || "Approve & post"}
            </button>
            <button
              type="button"
              disabled={cancel.isPending}
              onClick={() =>
                runAction(async () => {
                  await cancel.mutateAsync();
                  router.push("/billing/supplier-invoices");
                })
              }
              className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 dark:border-red-900 dark:bg-red-950 dark:text-red-300 dark:hover:bg-red-900 disabled:opacity-60"
            >
              <Ban className="h-4 w-4" />
              {t("cancel") || "Cancel"}
            </button>
          </>
        )}
        {invoice.status === "approved" && invoice.balance > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number"
              min={1}
              max={invoice.balance}
              value={payAmount || invoice.balance}
              onChange={(e) => setPayAmount(Number(e.target.value) || 0)}
              className="w-32 rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
            <select
              value={payMethod}
              onChange={(e) =>
                setPayMethod(
                  e.target.value as "bank" | "cash" | "mpesa" | "cheque",
                )
              }
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <option value="bank">Bank</option>
              <option value="cash">Cash</option>
              <option value="mpesa">M-Pesa</option>
              <option value="cheque">Cheque</option>
            </select>
            <input
              type="text"
              placeholder={t("reference") || "Reference"}
              value={payReference}
              onChange={(e) => setPayReference(e.target.value)}
              className="w-40 rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={pay.isPending}
              onClick={() =>
                runAction(() =>
                  pay.mutateAsync({
                    amount: payAmount || invoice.balance,
                    payment_method: payMethod,
                    reference: payReference || null,
                  }),
                )
              }
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              <Wallet className="h-4 w-4" />
              {t("recordPayment") || "Record payment"}
            </button>
          </div>
        )}
      </div>

      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {actionError}
        </div>
      )}

      {invoice.notes && (
        <div className="rounded-xl border border-border bg-card p-4 text-sm shadow-[var(--shadow-card)]">
          <div className="text-xs uppercase text-muted-foreground">
            {t("notes") || "Notes"}
          </div>
          <p className="mt-1 whitespace-pre-wrap text-foreground">
            {invoice.notes}
          </p>
        </div>
      )}

      {(invoice.gl_transaction_id || invoice.gl_payment_transaction_id) && (
        <div className="rounded-xl border border-border bg-card p-4 text-xs shadow-[var(--shadow-card)]">
          <div className="font-semibold uppercase text-muted-foreground">
            {tc("auditTrail") || "GL audit trail"}
          </div>
          {invoice.gl_transaction_id && (
            <div className="mt-1 font-mono">
              Approval txn: {invoice.gl_transaction_id}
            </div>
          )}
          {invoice.gl_payment_transaction_id && (
            <div className="mt-1 font-mono">
              Payment txn: {invoice.gl_payment_transaction_id}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
