import type { OperationResponse } from "../../lib/api/contracts";

const DEFAULT_BATCH_SIZE = 20;
const DUPLICATED_MESSAGE = "任务已在队列中";

export interface BulkLibraryUpdateStats {
  total: number;
  processed: number;
  added: number;
  duplicated: number;
  failed: number;
}

export interface BulkLibraryUpdateResult {
  stats: BulkLibraryUpdateStats;
  addedIds: string[];
}

interface BulkLibraryUpdateOptions<TItem> {
  items: TItem[];
  batchSize?: number;
  enqueue: (item: TItem) => Promise<OperationResponse>;
  getId: (item: TItem) => string;
  onProgress?: (stats: BulkLibraryUpdateStats) => void;
}

function createInitialStats(total: number): BulkLibraryUpdateStats {
  return {
    total,
    processed: 0,
    added: 0,
    duplicated: 0,
    failed: 0,
  };
}

function yieldToMainThread() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });
}

export async function enqueueLibraryItemsInBatches<TItem>({
  items,
  batchSize = DEFAULT_BATCH_SIZE,
  enqueue,
  getId,
  onProgress,
}: BulkLibraryUpdateOptions<TItem>): Promise<BulkLibraryUpdateResult> {
  const normalizedBatchSize = Number.isFinite(batchSize)
    ? Math.max(1, Math.floor(batchSize))
    : DEFAULT_BATCH_SIZE;
  const stats = createInitialStats(items.length);
  const addedIds: string[] = [];

  for (let start = 0; start < items.length; start += normalizedBatchSize) {
    const batch = items.slice(start, start + normalizedBatchSize);
    const settledResults = await Promise.allSettled(batch.map((item) => enqueue(item)));

    settledResults.forEach((result, index) => {
      stats.processed += 1;

      if (result.status === "fulfilled") {
        if (result.value.ok) {
          stats.added += 1;
          addedIds.push(getId(batch[index]));
          return;
        }

        if (result.value.message === DUPLICATED_MESSAGE) {
          stats.duplicated += 1;
          return;
        }
      }

      stats.failed += 1;
    });

    onProgress?.({ ...stats });
    await yieldToMainThread();
  }

  return { stats, addedIds };
}
