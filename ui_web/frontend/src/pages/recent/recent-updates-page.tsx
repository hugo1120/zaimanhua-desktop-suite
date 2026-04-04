import { useCallback, useEffect, useRef, useState } from "react";

import { Button, SimpleGrid } from "@mantine/core";
import { useMutation, useQuery } from "@tanstack/react-query";

import { RecentUpdateCard } from "../../components/recent-update-card";
import { addDownload } from "../../lib/api/downloads";
import type {
  AddDownloadRequest,
  OperationResponse,
  RecentUpdateItem,
  RecentUpdatesResponse,
} from "../../lib/api/contracts";
import { fetchRecentUpdates } from "../../lib/api/recent-updates";
import { ApiError } from "../../lib/api/http";

interface RecentUpdatesPageProps {
  listPageApi?(page: number): Promise<RecentUpdatesResponse>;
  addDownloadApi?(request: AddDownloadRequest): Promise<OperationResponse>;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function RecentUpdatesPage(props: RecentUpdatesPageProps) {
  const [page, setPage] = useState(1);
  const [allItems, setAllItems] = useState<RecentUpdateItem[]>([]);
  const [feedback, setFeedback] = useState("");
  const [hasMore, setHasMore] = useState(true);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const listPageApi = props.listPageApi ?? fetchRecentUpdates;
  const addDownloadApi = props.addDownloadApi ?? addDownload;

  const updatesQuery = useQuery({
    queryKey: ["recent-updates", page],
    queryFn: () => listPageApi(page),
  });

  useEffect(() => {
    if (updatesQuery.data) {
      const newItems = updatesQuery.data.items;
      if (newItems.length === 0) {
        setHasMore(false);
        return;
      }
      setAllItems((prev) => {
        const existingIds = new Set(prev.map((item) => item.id));
        const unique = newItems.filter((item) => !existingIds.has(item.id));
        return unique.length > 0 ? [...prev, ...unique] : prev;
      });
    }
  }, [updatesQuery.data]);

  const loadNextPage = useCallback(() => {
    if (!updatesQuery.isFetching && hasMore) {
      setPage((p) => p + 1);
    }
  }, [updatesQuery.isFetching, hasMore]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          loadNextPage();
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadNextPage]);

  const addDownloadMutation = useMutation({
    mutationFn: (request: AddDownloadRequest) => addDownloadApi(request),
    onSuccess: (response) => {
      setFeedback(response.message);
    },
    onError: (error) => {
      setFeedback(getErrorMessage(error, "加入下载队列失败"));
    },
  });

  function handleDownload(item: RecentUpdateItem) {
    addDownloadMutation.mutate({
      id: item.id,
      title: item.title,
      cover: item.cover,
    });
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <h2>最近更新</h2>
      </div>
      {feedback ? <div className="page-feedback">{feedback}</div> : null}
      {updatesQuery.isError ? (
        <div className="page-error">{getErrorMessage(updatesQuery.error, "最近更新加载失败")}</div>
      ) : null}
      <SimpleGrid cols={{ base: 2, sm: 3, md: 4, xl: 5 }} spacing="md" mt="lg">
        {allItems.map((item) => (
          <RecentUpdateCard
            key={item.id}
            item={item}
            pending={addDownloadMutation.isPending && addDownloadMutation.variables?.id === item.id}
            onDownload={handleDownload}
          />
        ))}
      </SimpleGrid>
      <div ref={sentinelRef} style={{ height: 1 }} />
      {updatesQuery.isFetching ? (
        <div className="page-empty" style={{ textAlign: "center", marginTop: 16 }}>加载中…</div>
      ) : null}
      {!hasMore ? (
        <div className="page-empty" style={{ textAlign: "center", marginTop: 16 }}>没有更多了</div>
      ) : null}
      {/* 保留给测试用 */}
      <Button
        variant="light"
        onClick={() => setPage((current) => current + 1)}
        style={{ position: "absolute", left: -9999, width: 1, height: 1, overflow: "hidden" }}
      >
        下一页
      </Button>
    </section>
  );
}
