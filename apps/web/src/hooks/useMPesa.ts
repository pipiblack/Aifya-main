"use client";

import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import type {
  STKPushApiRequest,
  STKPushResponse,
  MPesaTransactionStatus,
  MPesaStatus,
} from "@aifya/shared";

// ── STK Push ────────────────────────────────────────────────────────────────

/**
 * Hook for initiating an M-Pesa STK Push payment.
 *
 * @returns Mutation for STK Push initiation
 */
export function useSTKPush() {
  return useOfflineMutation<STKPushResponse, STKPushApiRequest>({
    mutationFn: (data: STKPushApiRequest) =>
      apiClient.post<STKPushResponse>("/mpesa/stk-push", data),
    offlineKey: "mpesa-stk-push",
  });
}

// ── STK Status ──────────────────────────────────────────────────────────────

/**
 * Hook for querying STK Push transaction status.
 *
 * @param checkoutRequestId - Checkout request ID from STK Push
 * @param enabled - Whether to poll (set true after STK push)
 * @returns Query result with transaction status
 */
export function useSTKStatus(checkoutRequestId: string | null, enabled: boolean = false) {
  return useOfflineQuery<MPesaTransactionStatus>({
    queryKey: ["mpesa", "stk-status", checkoutRequestId],
    queryFn: () =>
      apiClient.get<MPesaTransactionStatus>(
        `/mpesa/stk-status/${checkoutRequestId}`,
      ),
    enabled: enabled && !!checkoutRequestId,
    refetchInterval: 5_000, // Poll every 5s while waiting
  });
}

// ── M-Pesa Status ───────────────────────────────────────────────────────────

/**
 * Hook for checking M-Pesa configuration status.
 *
 * @returns Query result with M-Pesa config status
 */
export function useMPesaStatus() {
  return useOfflineQuery<MPesaStatus>({
    queryKey: ["mpesa", "status"],
    queryFn: () => apiClient.get<MPesaStatus>("/mpesa/status"),
    refetchInterval: 60_000,
  });
}
