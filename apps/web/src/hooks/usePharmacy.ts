"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  PharmacyQueueResponse,
  Dispensing,
  DispenseRequest,
  InventoryListResponse,
  InventoryReceiveRequest,
  InventoryAdjustRequest,
  PharmacyItem,
  PharmacyItemCreate,
  PharmacyItemUpdate,
  StockAlert,
  StockSummaryResponse,
  StockTransaction,
  StockReceiptRequest,
  StockAdjustmentRequest,
} from "@aifya/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// ── Queue ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching the pharmacy dispensing queue.
 *
 * @returns Query result with pending prescriptions
 */
export function usePharmacyQueue() {
  return useOfflineQuery<PharmacyQueueResponse>({
    queryKey: ["pharmacy", "queue"],
    queryFn: () => apiClient.get<PharmacyQueueResponse>("/pharmacy/queue"),
    refetchInterval: 15_000,
  });
}

// ── Dispensing ───────────────────────────────────────────────────────────

/**
 * Hook for dispensing a prescription.
 *
 * @returns Mutation for dispensing
 */
export function useDispense() {
  const queryClient = useQueryClient();

  return useOfflineMutation<Dispensing, DispenseRequest>(
    {
      mutationFn: (data: DispenseRequest) =>
        apiClient.post<Dispensing>("/pharmacy/dispense", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
        queryClient.invalidateQueries({ queryKey: ["encounters"] });
      },
    },
    { url: `${API_URL}/pharmacy/dispense`, method: "POST" }
  );
}

// ── Inventory ────────────────────────────────────────────────────────────

/**
 * Hook for fetching pharmacy inventory with search and pagination.
 *
 * @param query - Optional search string
 * @param page - Page number
 * @param pageSize - Items per page
 * @returns Query result with inventory list
 */
export function usePharmacyInventory(
  query?: string,
  page: number = 1,
  pageSize: number = 50
) {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (query) {
    params["q"] = query;
  }

  return useOfflineQuery<InventoryListResponse>({
    queryKey: ["pharmacy", "inventory", query ?? "", page, pageSize],
    queryFn: () =>
      apiClient.get<InventoryListResponse>("/pharmacy/inventory", params),
  });
}

/**
 * Hook for creating a pharmacy inventory item.
 *
 * @returns Mutation for creating inventory item
 */
export function useCreatePharmacyItem() {
  const queryClient = useQueryClient();

  return useOfflineMutation<PharmacyItem, PharmacyItemCreate>(
    {
      mutationFn: (data: PharmacyItemCreate) =>
        apiClient.post<PharmacyItem>("/pharmacy/inventory", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy", "inventory"] });
      },
    },
    { url: `${API_URL}/pharmacy/inventory`, method: "POST" }
  );
}

/**
 * Hook for updating a pharmacy inventory item.
 *
 * @param itemId - PharmacyItem UUID
 * @returns Mutation for updating inventory item
 */
export function useUpdatePharmacyItem(itemId: string) {
  const queryClient = useQueryClient();

  return useOfflineMutation<PharmacyItem, PharmacyItemUpdate>(
    {
      mutationFn: (data: PharmacyItemUpdate) =>
        apiClient.patch<PharmacyItem>(`/pharmacy/inventory/${itemId}`, data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy", "inventory"] });
      },
    },
    { url: `${API_URL}/pharmacy/inventory/${itemId}`, method: "PATCH" }
  );
}

// ── Stock ────────────────────────────────────────────────────────────────

/**
 * Hook for receiving stock.
 *
 * @returns Mutation for stock receipt
 */
export function useReceiveStock() {
  const queryClient = useQueryClient();

  return useOfflineMutation<StockTransaction, StockReceiptRequest>(
    {
      mutationFn: (data: StockReceiptRequest) =>
        apiClient.post<StockTransaction>("/pharmacy/stock/receive", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    { url: `${API_URL}/pharmacy/stock/receive`, method: "POST" }
  );
}

/**
 * Hook for adjusting stock.
 *
 * @returns Mutation for stock adjustment
 */
export function useAdjustStock() {
  const queryClient = useQueryClient();

  return useOfflineMutation<StockTransaction, StockAdjustmentRequest>(
    {
      mutationFn: (data: StockAdjustmentRequest) =>
        apiClient.post<StockTransaction>("/pharmacy/stock/adjust", data, generateId()),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    { url: `${API_URL}/pharmacy/stock/adjust`, method: "POST" }
  );
}

// ── Alerts ───────────────────────────────────────────────────────────────

/**
 * Hook for fetching stock alerts (low stock, expiring, expired).
 *
 * @returns Query result with stock alerts
 */
export function useStockAlerts() {
  return useOfflineQuery<StockAlert[]>({
    queryKey: ["pharmacy", "alerts"],
    queryFn: () => apiClient.get<StockAlert[]>("/pharmacy/alerts"),
    refetchInterval: 60_000,
  });
}

// ── Top-up / stock-take on an existing item ──────────────────────────────

/**
 * Hook for topping up an EXISTING pharmacy item by URL-path id.
 *
 * Replaces the duplicate-creation workflow flagged by the May 2026 audit.
 *
 * @returns Mutation for stock top-up keyed by item id
 */
export function useReceiveForItem(itemId: string) {
  const queryClient = useQueryClient();
  return useOfflineMutation<StockTransaction, InventoryReceiveRequest>(
    {
      mutationFn: (data: InventoryReceiveRequest) =>
        apiClient.post<StockTransaction>(
          `/pharmacy/inventory/${itemId}/receive`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    {
      url: `${API_URL}/pharmacy/inventory/${itemId}/receive`,
      method: "POST",
    },
  );
}

/**
 * Hook for stock-take adjustment on an existing item.
 *
 * @returns Mutation keyed by item id
 */
export function useAdjustForItem(itemId: string) {
  const queryClient = useQueryClient();
  return useOfflineMutation<StockTransaction, InventoryAdjustRequest>(
    {
      mutationFn: (data: InventoryAdjustRequest) =>
        apiClient.post<StockTransaction>(
          `/pharmacy/inventory/${itemId}/adjust`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["pharmacy"] });
      },
    },
    {
      url: `${API_URL}/pharmacy/inventory/${itemId}/adjust`,
      method: "POST",
    },
  );
}

// ── Stock summary (Opening / Received / Sales / Closing) ─────────────────

/**
 * Hook for fetching Opening/Received/Sales/Closing stock summary in a date range.
 *
 * @param startDate - ISO date (YYYY-MM-DD); inclusive
 * @param endDate - ISO date (YYYY-MM-DD); inclusive
 * @param itemId - Optional single-item filter
 * @returns Query result with summary rows
 */
export function useStockSummary(
  startDate?: string,
  endDate?: string,
  itemId?: string,
) {
  const qs = new URLSearchParams();
  if (startDate) qs.set("start_date", startDate);
  if (endDate) qs.set("end_date", endDate);
  if (itemId) qs.set("item_id", itemId);
  const path = `/pharmacy/inventory/stock-summary${qs.toString() ? `?${qs.toString()}` : ""}`;
  return useOfflineQuery<StockSummaryResponse>({
    queryKey: ["pharmacy", "stock-summary", startDate, endDate, itemId],
    queryFn: () => apiClient.get<StockSummaryResponse>(path),
    enabled: !!startDate && !!endDate,
  });
}
