"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Building2, Plus, Search, Trash2 } from "lucide-react";
import { Link } from "@/i18n/routing";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageSkeleton } from "@/components/ui/Skeleton";
import {
  useSuppliers,
  useCreateSupplier,
  type SupplierCreate,
} from "@/hooks/useSuppliers";

/**
 * Suppliers list — manage vendor records used by procurement and supplier
 * invoicing. Customer/patient records live separately under /patients per
 * audit 2026-05-14.
 *
 * @returns Suppliers page
 */
export default function SuppliersPage() {
  const t = useTranslations("billing");
  const tc = useTranslations("common");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<SupplierCreate>({ name: "" });

  const { data, isLoading } = useSuppliers(search, page);
  const create = useCreateSupplier();

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(form);
    setForm({ name: "" });
    setShowCreate(false);
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Building2}
        title={t("suppliers") || "Suppliers"}
        breadcrumbs={[
          { label: t("dashboard"), href: "/billing" },
          { label: t("suppliers") || "Suppliers" },
        ]}
        actions={
          <button
            type="button"
            onClick={() => setShowCreate((v) => !v)}
            className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("newSupplier") || "New supplier"}
          </button>
        }
      />

      {/* Search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder={t("searchSuppliers") || "Search suppliers"}
            className="w-full rounded-lg border border-border bg-card pl-9 pr-3 py-2 text-sm shadow-sm"
          />
        </div>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
        >
          <h3 className="mb-3 font-semibold text-foreground">
            {t("newSupplier") || "New supplier"}
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <input
              required
              placeholder={t("supplierName") || "Name"}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <input
              placeholder={t("contactPerson") || "Contact person"}
              value={form.contact_person ?? ""}
              onChange={(e) =>
                setForm({ ...form, contact_person: e.target.value })
              }
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <input
              placeholder={t("phone") || "Phone"}
              value={form.phone ?? ""}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <input
              placeholder={t("email") || "Email"}
              value={form.email ?? ""}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <input
              placeholder="KRA PIN"
              value={form.kra_pin ?? ""}
              onChange={(e) => setForm({ ...form, kra_pin: e.target.value })}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <input
              placeholder={t("bankAccount") || "Bank account"}
              value={form.bank_account ?? ""}
              onChange={(e) =>
                setForm({ ...form, bank_account: e.target.value })
              }
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
            <button
              type="submit"
              disabled={!form.name || create.isPending}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {tc("save")}
            </button>
          </div>
        </form>
      )}

      {/* List */}
      {isLoading ? (
        <PageSkeleton />
      ) : !data?.items.length ? (
        <EmptyState
          icon={Building2}
          title={t("noSuppliers") || "No suppliers yet"}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("supplierCode") || "Code"}</th>
                <th className="px-4 py-3">{t("name") || "Name"}</th>
                <th className="px-4 py-3">
                  {t("contactPerson") || "Contact"}
                </th>
                <th className="px-4 py-3">{t("phone") || "Phone"}</th>
                <th className="px-4 py-3">{t("email") || "Email"}</th>
                <th className="px-4 py-3">{t("statusLabel") || "Status"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.items.map((s) => (
                <tr key={s.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      href={`/billing/suppliers/${s.id}`}
                      className="text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {s.supplier_code ?? s.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">
                    {s.name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.contact_person ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.phone ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {s.email ?? "—"}
                  </td>
                  <td className="px-4 py-3">
                    {s.is_active ? (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-950 dark:text-green-300">
                        {t("active") || "Active"}
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        <Trash2 className="mr-1 inline h-3 w-3" />
                        {t("inactive") || "Inactive"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
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
