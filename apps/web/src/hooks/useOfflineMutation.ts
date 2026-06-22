"use client";

import { useMutation, type UseMutationOptions, type UseMutationResult } from "@tanstack/react-query";
import { queueMutation } from "@/lib/offline-store";
import { generateId } from "@/lib/utils";

type OfflineMutationOptions<TData, TVariables> = UseMutationOptions<
  TData,
  Error,
  TVariables
> & {
  offlineKey?: string;
  generateOfflineId?: (variables: TVariables) => string;
};

type OfflineConfig = {
  url?: string;
  method?: string;
  storeName?: string;
  generateId?: () => string;
};

/**
 * TanStack Mutation wrapper that queues mutations when offline.
 * Per CLAUDE.md: every mutation must queue locally if offline, sync when connected.
 *
 * @param options - Standard TanStack Mutation options
 * @param offlineConfig - URL and method for offline queue
 * @returns Mutation result
 */
export function useOfflineMutation<TData, TVariables>(
  options: OfflineMutationOptions<TData, TVariables>,
  offlineConfig: OfflineConfig | string = {}
): UseMutationResult<TData, Error, TVariables> {
  const { offlineKey, generateOfflineId, ...mutationOptions } = options;
  const config =
    typeof offlineConfig === "string" ? { storeName: offlineConfig } : offlineConfig;
  const queueKey = config.storeName ?? offlineKey ?? "mutation";

  return useMutation<TData, Error, TVariables>({
    ...mutationOptions,
    mutationFn: async (variables: TVariables) => {
      if (!navigator.onLine) {
        await queueMutation({
          id: generateOfflineId?.(variables) ?? config.generateId?.() ?? generateId(),
          url: config.url ?? `/offline/${queueKey}`,
          method: config.method ?? "POST",
          body: JSON.stringify(variables),
          headers: { "Content-Type": "application/json" },
          createdAt: new Date().toISOString(),
        });
        // Return optimistic data for offline
        return variables as unknown as TData;
      }

      if (mutationOptions.mutationFn) {
        return (mutationOptions.mutationFn as (variables: TVariables) => Promise<TData>)(variables);
      }
      throw new Error("No mutationFn provided");
    },
  });
}
