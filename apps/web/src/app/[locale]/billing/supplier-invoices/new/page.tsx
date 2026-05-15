"use client";

import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/routing";
import { useTranslations } from "next-intl";
import { FileText, Plus, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatKES } from "@/lib/utils";
import {
  useSuppliers,
  useCreateSupplierInvoice,
  type SupplierInvoiceLine,
} from "@/hooks/useSuppliers";

/** Default expense accounts users can pick from per line. Matches seeded CoA. */
const EXPENSE_ACCOUNTS = [
  { code: "5000", label: "5000 — Salaries & Wages" },
  { code: "5010", label: "5010 — Cost of Goods Sold" },
  { code: "5020", label: "5020 — Depreciation Expense" },
  { code: "5030", label: "5030 — Operating Expenses" },
];

/**
 * Create-supplier-invoice page. Always starts as draft.
 *
 * @returns Create supplier invoice page
 */
export default function NewSupplierInvoicePage() {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedSupplier = searchParams?.get("supplier") ?? "";

  const { data: suppliers } = useSuppliers(undefined, 1, 200);
  const create = useCreateSupplierInvoice();

  const [supplierId, setSupplierId] = useState<string>(preselectedSupplier);
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [invoiceDate, setInvoiceDate] = useState<string>(
    () => new Date().toISOString().slice(0, 10),
  );
  const [dueDate, setDueDate] = useState<string>("");
  const [vatAmount, setVatAmount] = useState<number>(0);
  const [whtAmount, setWhtAmount] = useState<number>(0);
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<SupplierInvoiceLine[]>([
    { description: "", quantity: 1, unit_price: 0, account_code: "5030" },
  ]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (preselectedSupplier) setSupplierId(preselectedSupplier);
  }, [preselectedSupplier]);

  const subtotal = useMemo(
    () => lines.reduce((sum, l) => sum + l.quantity * l.unit_price, 0),
    [lines],
  );
  const total = subtotal + vatAmount - whtAmount;

  const updateLine = (idx: number, patch: Partial<SupplierInvoiceLine>) => {
    setLines((prev) =>
      prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)),
    );
  };
  const removeLine = (idx: number) => {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  };
  const addLine = () => {
    setLines((prev) => [
      ...prev,
      { description: "", quantity: 1, unit_price: 0, account_code: "5030" },
    ]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!supplierId) {
      setError(t("selectSupplier") || "Please select a supplier");
      return;
    }
    if (!invoiceNumber.trim()) {
      setError(t("invoiceNumberRequired") || "Invoice number is required");
      return;
    }
    if (lines.length === 0 || lines.some((l) => !l.description.trim())) {
      setError(t("eachLineNeedsDescription") || "Each line needs a description");
      return;
    }
    try {
      const created = await create.mutateAsync({
        supplier_id: supplierId,
        invoice_number: invoiceNumber,
        invoice_date: invoiceDate,
        due_date: dueDate || null,
        vat_amount: vatAmount,
        wht_amount: whtAmount,
        notes: notes || null,
        lines,
      });
      router.push(`/billing/supplier-invoices/${created.id}`);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message);
    }
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={FileText}
        title={t("newSupplierInvoice") || "New supplier invoice"}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          {
            label: t("supplierInvoices") || "Supplier invoices",
            href: "/billing/supplier-invoices",
          },
          { label: t("new") || "New" },
        ]}
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("supplier") || "Supplier"}
            </label>
            <select
              required
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <option value="">{t("selectSupplier") || "Select supplier"}</option>
              {suppliers?.items.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("invoiceNumber") || "Invoice #"}
            </label>
            <input
              required
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("invoiceDate") || "Invoice date"}
            </label>
            <input
              type="date"
              required
              value={invoiceDate}
              onChange={(e) => setInvoiceDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("dueDate") || "Due date"}
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("vatAmount") || "VAT amount (cents)"}
            </label>
            <input
              type="number"
              min={0}
              value={vatAmount}
              onChange={(e) => setVatAmount(Number(e.target.value) || 0)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">
              {t("whtAmount") || "Withholding tax (cents)"}
            </label>
            <input
              type="number"
              min={0}
              value={whtAmount}
              onChange={(e) => setWhtAmount(Number(e.target.value) || 0)}
              className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* Lines */}
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="font-semibold text-foreground">
              {t("lineItems") || "Line items"}
            </h3>
            <button
              type="button"
              onClick={addLine}
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-3 w-3" />
              {t("addLine") || "Add line"}
            </button>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2">{t("description") || "Description"}</th>
                <th className="px-4 py-2 w-24">{t("quantity") || "Qty"}</th>
                <th className="px-4 py-2 w-40">
                  {t("unitPrice") || "Unit price"}
                </th>
                <th className="px-4 py-2 w-56">{t("account") || "Account"}</th>
                <th className="px-4 py-2 w-32 text-right">
                  {t("total") || "Total"}
                </th>
                <th className="px-2 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {lines.map((line, idx) => (
                <tr key={idx}>
                  <td className="px-4 py-2">
                    <input
                      required
                      value={line.description}
                      onChange={(e) =>
                        updateLine(idx, { description: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      type="number"
                      min={1}
                      value={line.quantity}
                      onChange={(e) =>
                        updateLine(idx, {
                          quantity: Math.max(1, Number(e.target.value) || 1),
                        })
                      }
                      className="w-full rounded-lg border border-border bg-background px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <input
                      type="number"
                      min={0}
                      value={line.unit_price}
                      onChange={(e) =>
                        updateLine(idx, {
                          unit_price: Math.max(0, Number(e.target.value) || 0),
                        })
                      }
                      className="w-full rounded-lg border border-border bg-background px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <select
                      value={line.account_code}
                      onChange={(e) =>
                        updateLine(idx, { account_code: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-2 py-1 text-sm"
                    >
                      {EXPENSE_ACCOUNTS.map((a) => (
                        <option key={a.code} value={a.code}>
                          {a.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2 text-right font-medium">
                    {formatKES(line.quantity * line.unit_price)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    {lines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLine(idx)}
                        className="rounded-lg p-1 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
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
              <span className="text-muted-foreground">{t("subtotal") || "Subtotal"}</span>
              <span className="font-medium">{formatKES(subtotal)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-muted-foreground">VAT</span>
              <span className="font-medium">{formatKES(vatAmount)}</span>
            </div>
            <div className="flex justify-between gap-8">
              <span className="text-muted-foreground">WHT</span>
              <span className="font-medium">- {formatKES(whtAmount)}</span>
            </div>
            <div className="mt-2 flex justify-between gap-8 border-t border-border pt-2 text-base">
              <span className="font-semibold">{t("total") || "Total"}</span>
              <span className="font-bold text-foreground">{formatKES(total)}</span>
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs uppercase text-muted-foreground">
            {t("notes") || "Notes"}
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
          />
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground hover:bg-muted"
          >
            {tc("cancel")}
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            {tc("save")}
          </button>
        </div>
      </form>
    </div>
  );
}
