"use client";

import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Building2, ChevronLeft, FileText } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatKES } from "@/lib/utils";
import {
  useSupplier,
  useSupplierInvoicesForSupplier,
} from "@/hooks/useSuppliers";

/**
 * Supplier detail page — supplier profile and invoice history.
 *
 * @returns Supplier detail page
 */
export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const supplierId = params?.id ?? "";
  const t = useTranslations("billing");

  const { data: supplier, isLoading } = useSupplier(supplierId);
  const { data: invoices } = useSupplierInvoicesForSupplier(supplierId);

  if (isLoading) return <PageSkeleton />;
  if (!supplier) {
    return (
      <div className="p-6 lg:p-8">
        <EmptyState
          icon={Building2}
          title={t("supplierNotFound") || "Supplier not found"}
        />
        <div className="mt-4">
          <Link
            href="/billing/suppliers"
            className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            <ChevronLeft className="h-4 w-4" />
            {t("backToSuppliers") || "Back to suppliers"}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Building2}
        title={supplier.name}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          { label: t("suppliers") || "Suppliers", href: "/billing/suppliers" },
          { label: supplier.name },
        ]}
      />

      {/* Supplier profile */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ProfileCard label="Code" value={supplier.supplier_code} mono />
        <ProfileCard label="Contact" value={supplier.contact_person} />
        <ProfileCard label="Phone" value={supplier.phone} />
        <ProfileCard label="Email" value={supplier.email} />
        <ProfileCard label="KRA PIN" value={supplier.kra_pin} mono />
        <ProfileCard label="Bank account" value={supplier.bank_account} mono />
        <ProfileCard label="Address" value={supplier.address} />
        <ProfileCard label="Payment terms" value={supplier.payment_terms} />
        <ProfileCard label="Category" value={supplier.category} />
      </div>

      {/* Invoice history */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="font-semibold text-foreground">
            {t("invoiceHistory") || "Invoice history"}
          </h3>
          <Link
            href={`/billing/supplier-invoices/new?supplier=${supplier.id}`}
            className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
          >
            <FileText className="h-3 w-3" />
            {t("newInvoice") || "New invoice"}
          </Link>
        </div>
        {!invoices?.items.length ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            {t("noInvoicesForSupplier") || "No invoices for this supplier yet."}
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("reference") || "Reference"}</th>
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
              {invoices.items.map((inv) => (
                <tr key={inv.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      href={`/billing/supplier-invoices/${inv.id}`}
                      className="text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {inv.our_reference}
                    </Link>
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
                    <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function ProfileCard({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div
        className={`mt-1 text-sm text-foreground ${mono ? "font-mono" : ""}`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}
