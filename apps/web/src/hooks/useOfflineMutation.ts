"use client";

import { useMutation, type UseMutationOptions, type UseMutationResult } from "@tanstack/react-query";
import { queueMutation } from "@/lib/offline-store";
import { generateId } from "@/lib/utils";

/**
 * TanStack Mutation wrapper that queues mutations when offline.
 * Per CLAUDE.md: every mutation must queue locally if offline, sync when connected.
 *
 * @param options - Standard TanStack Mutation options
 * @param offlineConfig - URL and method for offline queue
 * @returns Mutation result
 */
export function useOfflineMutation<TData, TVariables>(
  options: UseMutationOptions<TData, Error, TVariables>,
  offlineConfig: { url: string; method: string }
): UseMutationResult<TData, Error, TVariables> {
  return useMutation<TData, Error, TVariables>({
    ...options,
    mutationFn: async (variables: TVariables) => {
      if (!navigator.onLine) {
        await queueMutation({
          id: generateId(),
          url: offlineConfig.url,
          method: offlineConfig.method,
          body: JSON.stringify(variables),
          headers: { "Content-Type": "application/json" },
          createdAt: new Date().toISOString(),
        });
        // Return optimistic data for offline
        return variables as unknown as TData;
      }

      if (options.mutationFn) {
        return options.mutationFn(variables);
      }
      throw new Error("No mutationFn provided");
    },
  });
}
