"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { apiFetch } from "@/lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Types ───────────────────────────────────────────────────────────────────

export interface Supplier {
  id: string;
  name: string;
  supplier_code: string | null;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  kra_pin: string | null;
  bank_account: string | null;
  payment_terms: string | null;
  category: string | null;
  rating: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

export interface SupplierListResponse {
  items: Supplier[];
  total: number;
  page: number;
  page_size: number;
}

export interface SupplierCreate {
  name: string;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  kra_pin?: string | null;
  bank_account?: string | null;
  payment_terms?: string | null;
  category?: string | null;
  notes?: string | null;
}

export interface SupplierUpdate extends Partial<SupplierCreate> {
  is_active?: boolean;
}

export interface SupplierInvoiceLine {
  id?: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total?: number;
  account_code: string;
  department_id?: string | null;
}

export interface SupplierInvoiceCreate {
  supplier_id: string;
  invoice_number: string;
  invoice_date: string; // YYYY-MM-DD
  due_date?: string | null;
  vat_amount?: number;
  wht_amount?: number;
  notes?: string | null;
  attachment_url?: string | null;
  lines: SupplierInvoiceLine[];
}

export interface SupplierInvoice {
  id: string;
  supplier_id: string;
  supplier_name: string | null;
  invoice_number: string;
  our_reference: string;
  invoice_date: string;
  due_date: string | null;
  subtotal: number;
  vat_amount: number;
  wht_amount: number;
  total: number;
  paid_amount: number;
  balance: number;
  status: "draft" | "received" | "approved" | "paid" | "cancelled";
  notes: string | null;
  attachment_url: string | null;
  approved_by: string | null;
  approved_at: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  gl_transaction_id: string | null;
  gl_payment_transaction_id: string | null;
  lines: SupplierInvoiceLine[];
  created_at: string;
}

export interface SupplierInvoiceListItem {
  id: string;
  our_reference: string;
  invoice_number: string;
  supplier_id: string;
  supplier_name: string | null;
  invoice_date: string;
  due_date: string | null;
  total: number;
  paid_amount: number;
  balance: number;
  status: SupplierInvoice["status"];
}

export interface SupplierInvoiceListResponse {
  items: SupplierInvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SupplierInvoicePayment {
  amount: number;
  payment_date?: string | null;
  payment_method?: "bank" | "cash" | "mpesa" | "cheque";
  reference?: string | null;
  notes?: string | null;
}

// ── Cache keys ──────────────────────────────────────────────────────────────

const KEYS = {
  all: ["suppliers"] as const,
  list: (search?: string, page?: number) =>
    [...KEYS.all, "list", search ?? "", page ?? 1] as const,
  one: (id: string) => [...KEYS.all, "one", id] as const,
  invoices: (status?: string, supplierId?: string, page?: number) =>
    ["supplier-invoices", "list", status ?? "", supplierId ?? "", page ?? 1] as const,
  invoice: (id: string) => ["supplier-invoices", "one", id] as const,
  supplierInvoices: (id: string) =>
    [...KEYS.one(id), "invoices"] as const,
};

// ── Supplier hooks ──────────────────────────────────────────────────────────

/** List suppliers (paginated, optional name search). */
export function useSuppliers(search?: string, page = 1, pageSize = 50) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return useOfflineQuery<SupplierListResponse>({
    queryKey: KEYS.list(search, page),
    queryFn: () => apiFetch(`/api/v1/suppliers?${params.toString()}`),
    staleTime: 30_000,
  });
}

/** Fetch a single supplier by id. */
export function useSupplier(supplierId: string) {
  return useOfflineQuery<Supplier>({
    queryKey: KEYS.one(supplierId),
    queryFn: () => apiFetch(`/api/v1/suppliers/${supplierId}`),
    enabled: !!supplierId,
  });
}

/** Create a new supplier. */
export function useCreateSupplier() {
  const qc = useQueryClient();
  return useOfflineMutation<Supplier, SupplierCreate>(
    {
      mutationFn: (data) =>
        apiFetch("/api/v1/suppliers", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
    },
    { url: `${API_URL}/suppliers`, method: "POST" },
  );
}

/** Update an existing supplier. */
export function useUpdateSupplier(supplierId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<Supplier, SupplierUpdate>(
    {
      mutationFn: (data) =>
        apiFetch(`/api/v1/suppliers/${supplierId}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: KEYS.all });
        qc.invalidateQueries({ queryKey: KEYS.one(supplierId) });
      },
    },
    { url: `${API_URL}/suppliers/${supplierId}`, method: "PATCH" },
  );
}

/** List invoices for a given supplier. */
export function useSupplierInvoicesForSupplier(supplierId: string, page = 1) {
  return useOfflineQuery<SupplierInvoiceListResponse>({
    queryKey: KEYS.supplierInvoices(supplierId),
    queryFn: () =>
      apiFetch(
        `/api/v1/suppliers/${supplierId}/invoices?page=${page}&page_size=50`,
      ),
    enabled: !!supplierId,
  });
}

// ── Supplier invoice hooks ──────────────────────────────────────────────────

/** List supplier invoices (paginated, optional status / supplier filter). */
export function useSupplierInvoices(
  statusFilter?: string,
  supplierId?: string,
  page = 1,
  pageSize = 50,
) {
  const params = new URLSearchParams();
  if (statusFilter) params.set("status", statusFilter);
  if (supplierId) params.set("supplier_id", supplierId);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return useOfflineQuery<SupplierInvoiceListResponse>({
    queryKey: KEYS.invoices(statusFilter, supplierId, page),
    queryFn: () => apiFetch(`/api/v1/supplier-invoices?${params.toString()}`),
    staleTime: 30_000,
  });
}

/** Fetch a single supplier invoice (with lines). */
export function useSupplierInvoice(id: string) {
  return useOfflineQuery<SupplierInvoice>({
    queryKey: KEYS.invoice(id),
    queryFn: () => apiFetch(`/api/v1/supplier-invoices/${id}`),
    enabled: !!id,
  });
}

/** Create a new draft supplier invoice. */
export function useCreateSupplierInvoice() {
  const qc = useQueryClient();
  return useOfflineMutation<SupplierInvoice, SupplierInvoiceCreate>(
    {
      mutationFn: (data) =>
        apiFetch("/api/v1/supplier-invoices", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
      },
    },
    { url: `${API_URL}/supplier-invoices`, method: "POST" },
  );
}

/** Approve and post a supplier invoice to the GL. */
export function useApproveSupplierInvoice(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SupplierInvoice, void>(
    {
      mutationFn: () =>
        apiFetch(`/api/v1/supplier-invoices/${id}/approve`, {
          method: "POST",
        }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
        qc.invalidateQueries({ queryKey: KEYS.invoice(id) });
      },
    },
    { url: `${API_URL}/supplier-invoices/${id}/approve`, method: "POST" },
  );
}

/** Record a payment against an approved supplier invoice. */
export function usePaySupplierInvoice(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SupplierInvoice, SupplierInvoicePayment>(
    {
      mutationFn: (data) =>
        apiFetch(`/api/v1/supplier-invoices/${id}/pay`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
        qc.invalidateQueries({ queryKey: KEYS.invoice(id) });
      },
    },
    { url: `${API_URL}/supplier-invoices/${id}/pay`, method: "POST" },
  );
}

/** Cancel a draft supplier invoice. */
export function useCancelSupplierInvoice(id: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SupplierInvoice, void>(
    {
      mutationFn: () =>
        apiFetch(`/api/v1/supplier-invoices/${id}/cancel`, {
          method: "POST",
        }),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
        qc.invalidateQueries({ queryKey: KEYS.invoice(id) });
      },
    },
    { url: `${API_URL}/supplier-invoices/${id}/cancel`, method: "POST" },
  );
}
