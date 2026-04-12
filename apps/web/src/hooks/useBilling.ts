"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  BillingSummary,
  InvoiceListResponse,
  InvoiceDetail,
  InvoiceResponse,
  InvoiceCreate,
  PaymentResponseType,
  PaymentCreate,
  InvoiceWaiveRequest,
} from "@aifya/shared";

// ── Dashboard Summary ───────────────────────────────────────────────────────

/**
 * Hook for fetching the billing dashboard summary.
 *
 * @returns Query result with billing summary
 */
export function useBillingSummary() {
  return useOfflineQuery<BillingSummary>({
    queryKey: ["billing", "summary"],
    queryFn: () => apiClient.get<BillingSummary>("/billing/summary"),
    refetchInterval: 30_000,
  });
}

// ── Invoice List ────────────────────────────────────────────────────────────

/**
 * Hook for fetching paginated invoice list.
 *
 * @param statusFilter - Optional status filter
 * @param page - Page number
 * @param pageSize - Items per page
 * @returns Query result with invoice list
 */
export function useInvoiceList(
  statusFilter?: string,
  page: number = 1,
  pageSize: number = 50
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (statusFilter) {
    params["status"] = statusFilter;
  }

  return useOfflineQuery<InvoiceListResponse>({
    queryKey: ["billing", "invoices", statusFilter ?? "", page, pageSize],
    queryFn: () =>
      apiClient.get<InvoiceListResponse>("/billing/invoices", params),
    refetchInterval: 15_000,
  });
}

// ── Invoice Detail ──────────────────────────────────────────────────────────

/**
 * Hook for fetching a single invoice with items.
 *
 * @param invoiceId - Invoice UUID
 * @returns Query result with invoice detail
 */
export function useInvoiceDetail(invoiceId: string) {
  return useOfflineQuery<InvoiceDetail>({
    queryKey: ["billing", "invoices", invoiceId],
    queryFn: () =>
      apiClient.get<InvoiceDetail>(`/billing/invoices/${invoiceId}`),
    enabled: !!invoiceId,
  });
}

// ── Create Invoice ──────────────────────────────────────────────────────────

/**
 * Hook for creating a new invoice with line items.
 *
 * @returns Mutation for invoice creation
 */
export function useCreateInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<InvoiceResponse, InvoiceCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<InvoiceResponse>(
          "/billing/invoices",
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    "billing-create-invoice"
  );
}

// ── Finalize Invoice ────────────────────────────────────────────────────────

/**
 * Hook for finalizing (locking) an invoice.
 *
 * @returns Mutation for finalization
 */
export function useFinalizeInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<InvoiceResponse, { invoice_id: string }>(
    {
      mutationFn: ({ invoice_id }) =>
        apiClient.post<InvoiceResponse>(
          `/billing/invoices/${invoice_id}/finalize`,
          {},
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    "billing-finalize-invoice"
  );
}

// ── Record Payment ──────────────────────────────────────────────────────────

/**
 * Hook for recording a payment against an invoice.
 *
 * @returns Mutation for payment recording
 */
export function useRecordPayment() {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    PaymentResponseType,
    PaymentCreate & { invoice_id: string }
  >(
    {
      mutationFn: ({ invoice_id, ...data }) =>
        apiClient.post<PaymentResponseType>(
          `/billing/invoices/${invoice_id}/pay`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    "billing-record-payment"
  );
}

// ── Waive Invoice ───────────────────────────────────────────────────────────

/**
 * Hook for waiving remaining invoice balance.
 *
 * @returns Mutation for waiver
 */
export function useWaiveInvoice() {
  const queryClient = useQueryClient();

  return useOfflineMutation<
    InvoiceResponse,
    InvoiceWaiveRequest & { invoice_id: string }
  >(
    {
      mutationFn: ({ invoice_id, ...data }) =>
        apiClient.post<InvoiceResponse>(
          `/billing/invoices/${invoice_id}/waive`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["billing"] });
      },
    },
    "billing-waive-invoice"
  );
}
