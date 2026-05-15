"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Package,
  Search,
  Plus,
  AlertTriangle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  PackagePlus,
  Download,
  Printer,
  FileSpreadsheet,
  FileText,
  X,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  usePharmacyInventory,
  useStockAlerts,
  useCreatePharmacyItem,
  useReceiveForItem,
  useStockSummary,
} from "@/hooks/usePharmacy";
import { formatKES, formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { PharmacyItem, StockSummaryRow } from "@aifya/shared";

const newItemSchema = z.object({
  drug_code: z.string().min(1),
  drug_name: z.string().min(1),
  generic_name: z.string().nullable().optional(),
  is_keml: z.boolean().optional(),
  dosage_form: z.string().nullable().optional(),
  strength: z.string().nullable().optional(),
  batch_number: z.string().nullable().optional(),
  current_quantity: z.coerce.number().min(0),
  unit_of_measure: z.string(),
  reorder_level: z.coerce.number().min(0),
  selling_price_cents: z.coerce.number().min(0).nullable().optional(),
  buying_price_cents: z.coerce.number().min(0).nullable().optional(),
  expiry_date: z.string().nullable().optional(),
  manufacturer: z.string().nullable().optional(),
  supplier: z.string().nullable().optional(),
  shelf_location: z.string().nullable().optional(),
});

type NewItemFormData = z.infer<typeof newItemSchema>;

const receiveSchema = z.object({
  quantity: z.coerce.number().min(1),
  batch_no: z.string().optional(),
  expiry_date: z.string().optional(),
  supplier: z.string().optional(),
  unit_cost: z.coerce.number().min(0).optional(),
  notes: z.string().optional(),
});

type ReceiveFormData = z.infer<typeof receiveSchema>;

type TabKey = "inventory" | "summary";

/**
 * Pharmacy inventory management page.
 *
 * Tabs:
 *   - Inventory: search & add catalogue items, top-up existing stock via the
 *     `Receive Stock` button (single-source-of-truth — no duplicate items).
 *   - Stock Summary: Opening / Received / Sales / Closing per item over a
 *     date range; exportable as PDF / Print / Excel (XLSX) / CSV per the
 *     May 2026 audit (pharmacy stock-control regulations).
 *
 * @returns Inventory management page
 */
export default function InventoryPage() {
  const t = useTranslations("pharmacy");
  const tc = useTranslations("common");
  const [tab, setTab] = useState<TabKey>("inventory");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [receiveItem, setReceiveItem] = useState<PharmacyItem | null>(null);
  const pageSize = 30;

  const { data: inventory, isLoading } = usePharmacyInventory(
    searchQuery || undefined,
    page,
    pageSize,
  );
  const { data: alerts } = useStockAlerts();
  const createItem = useCreatePharmacyItem();

  const totalPages = inventory ? Math.ceil(inventory.total / pageSize) : 0;

  const {
    register,
    handleSubmit,
    reset,
  } = useForm<NewItemFormData>({
    resolver: zodResolver(newItemSchema),
    defaultValues: {
      current_quantity: 0,
      reorder_level: 10,
      unit_of_measure: "tablet",
      is_keml: false,
    },
  });

  const onSubmit = (data: NewItemFormData) => {
    createItem.mutate(
      {
        ...data,
        expiry_date: data.expiry_date || undefined,
      },
      {
        onSuccess: () => {
          setShowAddForm(false);
          reset();
        },
      },
    );
  };

  const alertColors: Record<string, string> = {
    out_of_stock: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    low_stock:
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200",
    expired: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    expiring_soon:
      "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  };

  const alertLabels: Record<string, string> = {
    out_of_stock: "outOfStock",
    low_stock: "lowStock",
    expired: "expired",
    expiring_soon: "expiringSoon",
  };

  return (
    <div className="mx-auto max-w-6xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/pharmacy"
          className="mb-3 inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("queue")}
        </Link>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Package className="h-7 w-7 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">
              {t("inventoryManagement")}
            </h1>
          </div>
          {tab === "inventory" && (
            <button
              type="button"
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              {t("addItem")}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-2 border-b border-border">
        <button
          type="button"
          onClick={() => setTab("inventory")}
          className={cn(
            "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            tab === "inventory"
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          {t("inventory")}
        </button>
        <button
          type="button"
          onClick={() => setTab("summary")}
          className={cn(
            "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            tab === "summary"
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          {t("stockSummary")}
        </button>
      </div>

      {tab === "summary" ? (
        <StockSummaryView />
      ) : (
        <>
          {/* Stock alerts */}
          {alerts && alerts.length > 0 && (
            <div className="mb-4 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                {t("stockAlerts")} ({alerts.length})
              </h3>
              <div className="flex flex-wrap gap-2">
                {alerts.map((alert) => (
                  <span
                    key={`${alert.item_id}-${alert.alert_type}`}
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      alertColors[alert.alert_type],
                    )}
                  >
                    {alert.drug_name} —{" "}
                    {t(
                      alertLabels[alert.alert_type] as Parameters<typeof t>[0],
                    )}
                    {alert.alert_type === "low_stock" &&
                      ` (${alert.current_quantity})`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Add item form */}
          {showAddForm && (
            <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
              <h3 className="mb-4 font-semibold text-foreground">
                {t("addItem")}
              </h3>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("drugCode")}
                    </label>
                    <input
                      {...register("drug_code")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("drugName")}
                    </label>
                    <input
                      {...register("drug_name")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("genericName")}
                    </label>
                    <input
                      {...register("generic_name")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("strength")}
                    </label>
                    <input
                      {...register("strength")}
                      placeholder="e.g. 500mg"
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("currentStock")}
                    </label>
                    <input
                      type="number"
                      {...register("current_quantity")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("unitOfMeasure")}
                    </label>
                    <select
                      {...register("unit_of_measure")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    >
                      <option value="tablet">{t("tablet")}</option>
                      <option value="capsule">{t("capsule")}</option>
                      <option value="ml">ml</option>
                      <option value="vial">Vial</option>
                      <option value="tube">Tube</option>
                      <option value="sachet">{t("sachet")}</option>
                      <option value="bottle">Bottle</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("reorderLevel")}
                    </label>
                    <input
                      type="number"
                      {...register("reorder_level")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("sellingPrice")}
                    </label>
                    <input
                      type="number"
                      {...register("selling_price_cents")}
                      placeholder="KES cents"
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("batchNumber")}
                    </label>
                    <input
                      {...register("batch_number")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("expiryDate")}
                    </label>
                    <input
                      type="date"
                      {...register("expiry_date")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">
                      {t("shelfLocation")}
                    </label>
                    <input
                      {...register("shelf_location")}
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
                    />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 pb-1.5 text-sm text-foreground">
                      <input
                        type="checkbox"
                        {...register("is_keml")}
                        className="rounded border-input text-primary"
                      />
                      {t("keml")}
                    </label>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="submit"
                    disabled={createItem.isPending}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {createItem.isPending ? t("addingItem") : t("addItem")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddForm(false);
                      reset();
                    }}
                    className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
                  >
                    {tc("cancel")}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              placeholder={tc("searchPlaceholder")}
              className="w-full rounded-lg border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground shadow-sm"
            />
          </div>

          {/* Inventory table */}
          <div className="overflow-hidden rounded-xl border border-border shadow-[var(--shadow-card)]">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                    {t("drugCode")}
                  </th>
                  <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                    {t("drugName")}
                  </th>
                  <th className="hidden px-3 py-2.5 text-left font-medium text-muted-foreground md:table-cell">
                    {t("strength")}
                  </th>
                  <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">
                    {t("currentStock")}
                  </th>
                  <th className="hidden px-3 py-2.5 text-right font-medium text-muted-foreground sm:table-cell">
                    {t("sellingPrice")}
                  </th>
                  <th className="hidden px-3 py-2.5 text-left font-medium text-muted-foreground lg:table-cell">
                    {t("expiryDate")}
                  </th>
                  <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                    {t("stockAlerts")}
                  </th>
                  <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">
                    {tc("actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-8 text-center text-muted-foreground"
                    >
                      {tc("loading")}
                    </td>
                  </tr>
                ) : inventory?.items.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-8 text-center text-muted-foreground"
                    >
                      {tc("noResults")}
                    </td>
                  </tr>
                ) : (
                  inventory?.items.map((item) => {
                    const itemAlerts =
                      alerts?.filter((a) => a.item_id === item.id) ?? [];
                    return (
                      <tr key={item.id} className="hover:bg-muted/30">
                        <td className="px-3 py-2.5 font-mono text-xs text-primary">
                          {item.drug_code}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-foreground">
                              {item.drug_name}
                            </span>
                            {item.is_keml && (
                              <ShieldCheck className="h-3.5 w-3.5 text-green-500" />
                            )}
                          </div>
                          {item.generic_name && (
                            <p className="text-xs text-muted-foreground">
                              {item.generic_name}
                            </p>
                          )}
                        </td>
                        <td className="hidden px-3 py-2.5 text-muted-foreground md:table-cell">
                          {item.strength ?? "—"}
                        </td>
                        <td
                          className={cn(
                            "px-3 py-2.5 text-right font-medium",
                            item.current_quantity === 0
                              ? "text-red-600"
                              : item.current_quantity <= item.reorder_level
                                ? "text-yellow-600"
                                : "text-foreground",
                          )}
                        >
                          {item.current_quantity}
                        </td>
                        <td className="hidden px-3 py-2.5 text-right text-muted-foreground sm:table-cell">
                          {item.selling_price_cents != null
                            ? formatKES(item.selling_price_cents)
                            : "—"}
                        </td>
                        <td className="hidden px-3 py-2.5 text-muted-foreground lg:table-cell">
                          {item.expiry_date ? formatDate(item.expiry_date) : "—"}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap gap-1">
                            {itemAlerts.map((alert) => (
                              <span
                                key={alert.alert_type}
                                className={cn(
                                  "rounded-full px-1.5 py-0.5 text-xs font-medium",
                                  alertColors[alert.alert_type],
                                )}
                              >
                                {t(
                                  alertLabels[
                                    alert.alert_type
                                  ] as Parameters<typeof t>[0],
                                )}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => setReceiveItem(item)}
                            className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                          >
                            <PackagePlus className="h-3.5 w-3.5" />
                            {t("receiveStock")}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
                {tc("back")}
              </button>
              <span className="text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-50"
              >
                {tc("next")}
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}

      {receiveItem && (
        <ReceiveStockDialog
          item={receiveItem}
          onClose={() => setReceiveItem(null)}
        />
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Receive Stock dialog — top-up an EXISTING item
// ──────────────────────────────────────────────────────────────────────────

function ReceiveStockDialog({
  item,
  onClose,
}: {
  item: PharmacyItem;
  onClose: () => void;
}) {
  const t = useTranslations("pharmacy");
  const tc = useTranslations("common");
  const receive = useReceiveForItem(item.id);

  const { register, handleSubmit, formState: { errors } } = useForm<ReceiveFormData>({
    resolver: zodResolver(receiveSchema),
    defaultValues: { quantity: 0 },
  });

  const onSubmit = (data: ReceiveFormData) => {
    receive.mutate(
      {
        quantity: data.quantity,
        batch_no: data.batch_no || undefined,
        expiry_date: data.expiry_date || undefined,
        supplier: data.supplier || undefined,
        unit_cost: data.unit_cost ?? undefined,
        notes: data.notes || undefined,
      },
      {
        onSuccess: () => {
          onClose();
        },
      },
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="receive-stock-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2
            id="receive-stock-title"
            className="flex items-center gap-2 text-base font-semibold text-foreground"
          >
            <PackagePlus className="h-5 w-5 text-primary" />
            {t("receiveStock")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label={tc("close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mb-4 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{item.drug_name}</span>
          {item.strength ? ` · ${item.strength}` : ""}
          <span className="ml-2">
            ({tc("current")}: {item.current_quantity} {item.unit_of_measure})
          </span>
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("quantity")} *
            </label>
            <input
              type="number"
              min={1}
              autoFocus
              {...register("quantity")}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            />
            {errors.quantity && (
              <p className="mt-1 text-xs text-destructive">
                {errors.quantity.message}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("batchNumber")}
              </label>
              <input
                {...register("batch_no")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("expiryDate")}
              </label>
              <input
                type="date"
                {...register("expiry_date")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("supplier")}
              </label>
              <input
                {...register("supplier")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("buyingPrice")} (KES)
              </label>
              <input
                type="number"
                step="0.01"
                {...register("unit_cost")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {tc("notes")}
            </label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-input px-4 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={receive.isPending}
              className="rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {receive.isPending ? t("receiving") : t("receiveStock")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Stock summary tab — Opening / Received / Sales / Closing per item
// ──────────────────────────────────────────────────────────────────────────

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function escapeCsv(value: string | number): string {
  const s = String(value);
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function StockSummaryView() {
  const t = useTranslations("pharmacy");
  const tc = useTranslations("common");

  const today = useMemo(() => new Date(), []);
  const firstOfMonth = useMemo(
    () => new Date(today.getFullYear(), today.getMonth(), 1),
    [today],
  );

  const [startDate, setStartDate] = useState(toIsoDate(firstOfMonth));
  const [endDate, setEndDate] = useState(toIsoDate(today));

  const { data, isLoading } = useStockSummary(startDate, endDate);

  const headers = useMemo(
    () => [
      tc("code"),
      t("drugName"),
      t("unitOfMeasure"),
      t("openingStock"),
      t("receivedStock"),
      t("salesStock"),
      t("closingStock"),
    ],
    [t, tc],
  );

  const toRows = (rows: StockSummaryRow[]): (string | number)[][] =>
    rows.map((r) => [
      r.drug_code,
      r.item_name,
      r.unit,
      r.opening_stock,
      r.received_stock,
      r.sales_stock,
      r.closing_stock,
    ]);

  // CSV export — client-side blob download.
  const downloadCsv = () => {
    if (!data) return;
    const rows = [headers, ...toRows(data.rows)];
    const csv = rows.map((r) => r.map(escapeCsv).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `stock-summary-${startDate}-${endDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Excel export — emits SpreadsheetML 2003 (.xls). Opens cleanly in
  // Excel and LibreOffice, no extra dependency. Future enhancement: swap to
  // the `xlsx` npm package once added to apps/web.
  const downloadXlsx = () => {
    if (!data) return;
    const escapeXml = (s: string | number) =>
      String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    const xmlRows = [headers, ...toRows(data.rows)]
      .map(
        (row) =>
          `<Row>${row
            .map((cell) =>
              typeof cell === "number"
                ? `<Cell><Data ss:Type="Number">${cell}</Data></Cell>`
                : `<Cell><Data ss:Type="String">${escapeXml(cell)}</Data></Cell>`,
            )
            .join("")}</Row>`,
      )
      .join("");
    const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Stock Summary"><Table>${xmlRows}</Table></Worksheet>
</Workbook>`;
    const blob = new Blob([xml], { type: "application/vnd.ms-excel" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `stock-summary-${startDate}-${endDate}.xls`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // PDF export — open print-CSS-styled report in new window and trigger print
  // (user selects "Save as PDF" from the OS print dialog).
  const downloadPdf = () => {
    if (!data) return;
    const win = window.open("", "_blank", "noopener,noreferrer");
    if (!win) return;
    const tableRows = data.rows
      .map(
        (r) =>
          `<tr><td>${r.drug_code}</td><td>${r.item_name}</td><td>${r.unit}</td><td style="text-align:right">${r.opening_stock}</td><td style="text-align:right">${r.received_stock}</td><td style="text-align:right">${r.sales_stock}</td><td style="text-align:right;font-weight:600">${r.closing_stock}</td></tr>`,
      )
      .join("");
    win.document.write(`<!doctype html><html><head><title>Stock Summary ${startDate} to ${endDate}</title>
<style>
  body{font-family:system-ui,sans-serif;color:#111;margin:24px;}
  h1{font-size:18px;margin:0 0 4px 0;}
  .meta{color:#666;font-size:12px;margin-bottom:16px;}
  table{width:100%;border-collapse:collapse;font-size:11px;}
  th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;}
  th{background:#f3f4f6;}
  @media print { body{margin:12mm;} }
</style></head><body>
<h1>Pharmacy Stock Summary</h1>
<div class="meta">${startDate} — ${endDate} · ${data.rows.length} items</div>
<table>
  <thead><tr><th>${headers[0]}</th><th>${headers[1]}</th><th>${headers[2]}</th><th>${headers[3]}</th><th>${headers[4]}</th><th>${headers[5]}</th><th>${headers[6]}</th></tr></thead>
  <tbody>${tableRows}</tbody>
</table>
<script>window.addEventListener('load',()=>{setTimeout(()=>window.print(),100);});</script>
</body></html>`);
    win.document.close();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <label className="block">
          <span className="mb-1 block text-xs text-muted-foreground">
            {tc("startDate")}
          </span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted-foreground">
            {tc("endDate")}
          </span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
          />
        </label>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            disabled={!data}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <Printer className="h-4 w-4" />
            {tc("print")}
          </button>
          <button
            type="button"
            onClick={downloadPdf}
            disabled={!data}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <FileText className="h-4 w-4" />
            PDF
          </button>
          <button
            type="button"
            onClick={downloadXlsx}
            disabled={!data}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <FileSpreadsheet className="h-4 w-4" />
            Excel
          </button>
          <button
            type="button"
            onClick={downloadCsv}
            disabled={!data}
            className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            CSV
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-border shadow-[var(--shadow-card)]">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                {tc("code")}
              </th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                {t("drugName")}
              </th>
              <th className="px-3 py-2.5 text-left font-medium text-muted-foreground">
                {t("unitOfMeasure")}
              </th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">
                {t("openingStock")}
              </th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">
                {t("receivedStock")}
              </th>
              <th className="px-3 py-2.5 text-right font-medium text-muted-foreground">
                {t("salesStock")}
              </th>
              <th className="px-3 py-2.5 text-right font-semibold text-foreground">
                {t("closingStock")}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  {tc("loading")}
                </td>
              </tr>
            ) : !data || data.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  {tc("noResults")}
                </td>
              </tr>
            ) : (
              data.rows.map((r) => (
                <tr key={r.item_id} className="hover:bg-muted/30">
                  <td className="px-3 py-2.5 font-mono text-xs text-primary">
                    {r.drug_code}
                  </td>
                  <td className="px-3 py-2.5 font-medium text-foreground">
                    {r.item_name}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{r.unit}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {r.opening_stock}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-emerald-700 dark:text-emerald-400">
                    {r.received_stock}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-orange-700 dark:text-orange-400">
                    {r.sales_stock}
                  </td>
                  <td className="px-3 py-2.5 text-right font-semibold tabular-nums">
                    {r.closing_stock}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
