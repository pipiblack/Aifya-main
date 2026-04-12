import { getPendingMutations, removeMutation } from "./offline-store";

/**
 * Offline sync worker — replays queued mutations when connectivity returns.
 * Per CLAUDE.md: every mutation queues locally if offline, syncs when connected.
 */

let isSyncing = false;

/**
 * Process all pending offline mutations in FIFO order.
 * Retries failed mutations up to 3 times before skipping.
 * @returns Number of successfully synced mutations
 */
export async function syncPendingMutations(): Promise<number> {
  if (isSyncing || !navigator.onLine) return 0;

  isSyncing = true;
  let synced = 0;

  try {
    const pending = await getPendingMutations();

    for (const mutation of pending) {
      try {
        const token = localStorage.getItem("access_token");
        const headers: Record<string, string> = {
          ...mutation.headers,
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch(mutation.url, {
          method: mutation.method,
          headers,
          body: mutation.body,
        });

        if (response.ok || response.status === 409) {
          // 409 = idempotent duplicate — already processed
          await removeMutation(mutation.id);
          synced++;
        } else if (mutation.retries >= 3) {
          // Give up after 3 retries
          await removeMutation(mutation.id);
        }
      } catch {
        // Network error — will retry on next sync
        break;
      }
    }
  } finally {
    isSyncing = false;
  }

  return synced;
}

/**
 * Initialize the sync worker — listens for online events.
 * Call once on app startup.
 */
export function initSyncWorker(): void {
  // Sync when coming back online
  window.addEventListener("online", () => {
    syncPendingMutations();
  });

  // Periodic sync every 30 seconds
  setInterval(() => {
    if (navigator.onLine) {
      syncPendingMutations();
    }
  }, 30_000);

  // Initial sync
  if (navigator.onLine) {
    syncPendingMutations();
  }
}
