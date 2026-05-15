"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, Plus } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { formatKES } from "@/lib/utils";
import { useSupplierInvoices } from "@/hooks/useSuppliers";

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  received: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  approved: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  paid: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  cancelled: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

/**
 * Supplier invoice list page.
 *
 * @returns Supplier invoice list page
 */
export default function SupplierInvoicesPage() {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useSupplierInvoices(
    statusFilter || undefined,
    undefined,
    page,
  );

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={FileText}
        title={t("supplierInvoices") || "Supplier invoices"}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          { label: t("supplierInvoices") || "Supplier invoices" },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground shadow-sm"
            >
              <option value="">{t("filterAll")}</option>
              <option value="draft">{t("draft") || "Draft"}</option>
              <option value="received">{t("received") || "Received"}</option>
              <option value="approved">{t("approved") || "Approved"}</option>
              <option value="paid">{t("paid")}</option>
              <option value="cancelled">{t("cancelled") || "Cancelled"}</option>
            </select>
            <Link
              href="/billing/supplier-invoices/new"
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              {t("newSupplierInvoice") || "New supplier invoice"}
            </Link>
          </div>
        }
      />

      {isLoading ? (
        <PageSkeleton />
      ) : !data?.items.length ? (
        <EmptyState
          icon={FileText}
          title={t("noSupplierInvoices") || "No supplier invoices yet"}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("reference") || "Reference"}</th>
                <th className="px-4 py-3">{t("supplier") || "Supplier"}</th>
                <th className="px-4 py-3">
                  {t("invoiceNumber") || "Invoice #"}
                </th>
                <th className="px-4 py-3">{t("invoiceDate") || "Date"}</th>
                <th className="px-4 py-3">{t("dueDate") || "Due"}</th>
                <th className="px-4 py-3">{t("total") || "Total"}</th>
                <th className="px-4 py-3">{t("balance") || "Balance"}</th>
                <th className="px-4 py-3">{t("statusLabel") || "Status"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.items.map((inv) => (
                <tr key={inv.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      href={`/billing/supplier-invoices/${inv.id}`}
                      className="text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {inv.our_reference}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">
                    {inv.supplier_name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {inv.invoice_number}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {new Date(inv.invoice_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {inv.due_date
                      ? new Date(inv.due_date).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {formatKES(inv.total)}
                  </td>
                  <td className="px-4 py-3 text-amber-600 dark:text-amber-400">
                    {inv.balance > 0 ? formatKES(inv.balance) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_BADGE[inv.status] ?? STATUS_BADGE.draft
                      }`}
                    >
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > data.page_size && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:opacity-50"
          >
            {tc("back")}
          </button>
          <span className="text-sm text-muted-foreground">
            {page} / {Math.ceil(data.total / data.page_size)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(data.total / data.page_size)}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-foreground hover:bg-muted disabled:opacity-50"
          >
            {tc("next")}
          </button>
        </div>
      )}
    </div>
  );
}
