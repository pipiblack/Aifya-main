"use client";

import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";
import type {
  LabWorklistResponse,
  LabOrderWithResults,
  LabOrderDetail,
  LabResultDetail,
  LabResultEntry,
  LabResultVerify,
  CriticalNotifyRequest,
  SpecimenCollectRequest,
} from "@aifya/shared";

// ── Worklist ────────────────────────────────────────────────────────────────

/**
 * Hook for fetching the lab worklist with offline support.
 * Auto-refreshes every 15 seconds for real-time updates.
 *
 * @param statusFilter - Optional status filter
 * @returns Query result with worklist data
 */
export function useLabWorklist(statusFilter?: string) {
  const params: Record<string, string> = {};
  if (statusFilter) {
    params["status"] = statusFilter;
  }

  return useOfflineQuery<LabWorklistResponse>({
    queryKey: ["laboratory", "worklist", statusFilter ?? ""],
    queryFn: () =>
      apiClient.get<LabWorklistResponse>("/laboratory/worklist", params),
    refetchInterval: 15_000,
  });
}

// ── Order Detail ────────────────────────────────────────────────────────────

/**
 * Hook for fetching a lab order with all results.
 *
 * @param orderId - LabOrder UUID
 * @returns Query result with order detail
 */
export function useLabOrderDetail(orderId: string) {
  return useOfflineQuery<LabOrderWithResults>({
    queryKey: ["laboratory", "orders", orderId],
    queryFn: () =>
      apiClient.get<LabOrderWithResults>(`/laboratory/orders/${orderId}`),
    enabled: !!orderId,
  });
}

// ── Specimen Collection ─────────────────────────────────────────────────────

/**
 * Hook for recording specimen collection.
 *
 * @returns Mutation for specimen collection
 */
export function useCollectSpecimen() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabOrderDetail, SpecimenCollectRequest & { order_id: string }>(
    {
      mutationFn: ({ order_id, ...data }) =>
        apiClient.post<LabOrderDetail>(
          `/laboratory/orders/${order_id}/collect`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    "lab-collect-specimen"
  );
}

// ── Result Entry ────────────────────────────────────────────────────────────

/**
 * Hook for entering a lab result.
 *
 * @returns Mutation for result entry
 */
export function useEnterResult() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, LabResultEntry & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/enter`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    "lab-enter-result"
  );
}

// ── Result Verification ─────────────────────────────────────────────────────

/**
 * Hook for verifying (approving) a lab result.
 *
 * @returns Mutation for result verification
 */
export function useVerifyResult() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, LabResultVerify & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/verify`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    "lab-verify-result"
  );
}

// ── Critical Notification ───────────────────────────────────────────────────

/**
 * Hook for recording critical value notification.
 *
 * @returns Mutation for critical notification
 */
export function useNotifyCritical() {
  const queryClient = useQueryClient();

  return useOfflineMutation<LabResultDetail, CriticalNotifyRequest & { result_id: string }>(
    {
      mutationFn: ({ result_id, ...data }) =>
        apiClient.post<LabResultDetail>(
          `/laboratory/results/${result_id}/notify-critical`,
          data,
          generateId()
        ),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["laboratory"] });
      },
    },
    "lab-notify-critical"
  );
}
