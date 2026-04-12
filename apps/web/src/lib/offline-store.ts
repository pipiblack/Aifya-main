import { openDB, type IDBPDatabase } from "idb";

const DB_NAME = "aifya-offline";
const DB_VERSION = 1;

interface MutationQueueItem {
  id: string;
  url: string;
  method: string;
  body: string;
  headers: Record<string, string>;
  createdAt: string;
  retries: number;
}

/**
 * Open the IndexedDB database for offline storage.
 * @returns IDB database instance
 */
async function getDB(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("query-cache")) {
        db.createObjectStore("query-cache");
      }
      if (!db.objectStoreNames.contains("mutation-queue")) {
        const store = db.createObjectStore("mutation-queue", {
          keyPath: "id",
        });
        store.createIndex("createdAt", "createdAt");
      }
    },
  });
}

/**
 * Cache a query response for offline access.
 * @param key - Cache key (typically the query key)
 * @param data - Data to cache
 */
export async function cacheQueryData(key: string, data: unknown): Promise<void> {
  const db = await getDB();
  await db.put("query-cache", { data, cachedAt: new Date().toISOString() }, key);
}

/**
 * Retrieve cached query data.
 * @param key - Cache key
 * @returns Cached data or undefined
 */
export async function getCachedQueryData<T>(key: string): Promise<T | undefined> {
  const db = await getDB();
  const result = await db.get("query-cache", key);
  return result?.data as T | undefined;
}

/**
 * Queue a mutation for later sync when offline.
 * @param item - Mutation details
 */
export async function queueMutation(
  item: Omit<MutationQueueItem, "retries">
): Promise<void> {
  const db = await getDB();
  await db.put("mutation-queue", { ...item, retries: 0 });
}

/**
 * Get all pending mutations in creation order.
 * @returns Array of queued mutations
 */
export async function getPendingMutations(): Promise<MutationQueueItem[]> {
  const db = await getDB();
  return db.getAllFromIndex("mutation-queue", "createdAt");
}

/**
 * Remove a mutation from the queue after successful sync.
 * @param id - Mutation ID
 */
export async function removeMutation(id: string): Promise<void> {
  const db = await getDB();
  await db.delete("mutation-queue", id);
}
