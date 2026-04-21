import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button, SimpleGrid, TextInput, ActionIcon } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RecentUpdateCard } from "../../components/recent-update-card";
import { SearchResultCard } from "../../components/search-result-card";
import { addDownload } from "../../lib/api/downloads";
import type { AddDownloadRequest, RecentUpdatesResponse } from "../../lib/api/contracts";
import { fetchRecentUpdates } from "../../lib/api/recent-updates";
import { searchManga } from "../../lib/api/search";
import { ApiError } from "../../lib/api/http";

function IconSearch() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>; }
function IconRefresh() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1rem" width="1rem"><path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>; }

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

const MAX_CONSECUTIVE_DUPLICATE_RECENT_PAGES = 3;

export function SearchPage() {
  const queryClient = useQueryClient();
  const [inputKeyword, setInputKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [feedback, setFeedback] = useState("");
  const [addedIds, setAddedIds] = useState<string[]>([]);
  const [recentPage, setRecentPage] = useState(1);
  const [recentItems, setRecentItems] = useState<RecentUpdatesResponse["items"]>([]);
  const [recentHasMore, setRecentHasMore] = useState(true);
  const [isRefreshingRecent, setIsRefreshingRecent] = useState(false);
  const recentSentinelRef = useRef<HTMLDivElement>(null);
  const recentSeenIdsRef = useRef<Set<string>>(new Set());
  const recentDuplicatePagesRef = useRef(0);

  const searchQuery = useQuery({ queryKey: ["search", submittedKeyword], enabled: submittedKeyword.length > 0, queryFn: () => searchManga(submittedKeyword) });
  const recentQuery = useQuery({ queryKey: ["recent-updates", recentPage, isRefreshingRecent], enabled: submittedKeyword.length === 0, queryFn: () => fetchRecentUpdates(recentPage, isRefreshingRecent) });

  const addDownloadMutation = useMutation({
    mutationFn: (request: AddDownloadRequest) => addDownload(request),
    onSuccess: (res, vars) => { setFeedback(res.message); if (vars.id) setAddedIds(prev => [...prev, vars.id]); }
  });

  const handleSearch = (e: FormEvent) => { e.preventDefault(); setFeedback(""); setSubmittedKeyword(inputKeyword.trim()); };

  useEffect(() => {
    if (!recentQuery.data || submittedKeyword.length > 0) return;
    const { page, items } = recentQuery.data;
    if (page === 1) {
      recentDuplicatePagesRef.current = 0;
      recentSeenIdsRef.current = new Set(items.map((item) => item.id));
      setRecentItems(items);
      setRecentHasMore(items.length > 0);
    }
    else {
      if (items.length === 0) {
        recentDuplicatePagesRef.current = 0;
        setRecentHasMore(false);
      }
      else {
        const unique = items.filter(item => !recentSeenIdsRef.current.has(item.id));
        if (unique.length === 0) {
          recentDuplicatePagesRef.current += 1;
          if (recentDuplicatePagesRef.current >= MAX_CONSECUTIVE_DUPLICATE_RECENT_PAGES) {
            setRecentHasMore(false);
          } else {
            setRecentPage(p => p + 1);
          }
        } else {
          recentDuplicatePagesRef.current = 0;
          unique.forEach((item) => recentSeenIdsRef.current.add(item.id));
          setRecentItems(prev => [...prev, ...unique]);
        }
      }
    }
    if (isRefreshingRecent && !recentQuery.isFetching) setIsRefreshingRecent(false);
  }, [recentQuery.data, recentQuery.isFetching, recentPage, isRefreshingRecent, submittedKeyword]);

  useEffect(() => {
    if (submittedKeyword.length > 0 || !recentQuery.isError) return;
    setRecentHasMore(false);
    if (isRefreshingRecent) {
      setIsRefreshingRecent(false);
    }
  }, [recentQuery.isError, submittedKeyword, isRefreshingRecent]);

  useEffect(() => {
    if (submittedKeyword.length > 0) return;
    const observer = new IntersectionObserver((entries) => { if (entries[0]?.isIntersecting && !recentQuery.isFetching && recentHasMore) setRecentPage(p => p + 1); }, { rootMargin: "400px" });
    if (recentSentinelRef.current) observer.observe(recentSentinelRef.current);
    return () => observer.disconnect();
  }, [recentQuery.isFetching, recentHasMore, submittedKeyword]);

  return (
    <section className="page-container search-page">
      <div className={`search-console${submittedKeyword ? " search-console--compact" : ""}`}>
        {!submittedKeyword && (
          <div className="search-console__intro">
            <span className="search-console__eyebrow">Search Console</span>
            <h1 className="search-console__title">发现精彩漫画</h1>
            <p className="search-console__subtitle">输入作品名、作者或 ID，或者直接浏览最近更新推荐。</p>
          </div>
        )}

        <form className="search-console__form" onSubmit={handleSearch}>
          <TextInput
            className="search-console__field"
            classNames={{
              input: "search-console__input",
              section: "search-console__input-section",
            }}
            leftSection={<IconSearch />}
            placeholder="搜索作品名、作者或 ID..."
            value={inputKeyword}
            onChange={(e) => setInputKeyword(e.target.value)}
            size="xl"
            radius="xl"
            px="lg"
          />
          <Button className="search-console__submit" type="submit" radius="xl" size="lg" color="teal" loading={searchQuery.isFetching}>
            搜索
          </Button>
        </form>
      </div>

      {feedback && <div className="page-feedback">{feedback}</div>}

      {submittedKeyword ? (
        <>
          <div className="section-header search-section-header">
            <div className="section-header__title-group">
              <span className="section-header__eyebrow">Search Results</span>
              <div className="section-header__headline-row">
                <h2 className="section-header__title">搜索结果</h2>
                <span className="section-header__count">{searchQuery.data?.items.length || 0} 项</span>
              </div>
              <div className="section-header__meta-row">
                <span className="section-header__keyword">{submittedKeyword}</span>
                <span className="section-header__summary">已切换到精准搜索视图</span>
              </div>
            </div>
            <div className="section-header__actions">
              <Button className="section-header__action" variant="light" color="gray" size="sm" radius="xl" onClick={() => setSubmittedKeyword("")}>
                返回推荐
              </Button>
            </div>
          </div>
          <SimpleGrid className="search-page__grid" cols={{ base: 2, sm: 3, md: 4, xl: 5 }} spacing="md">
            {searchQuery.data?.items.map(item => (
              <SearchResultCard key={item.id} item={item} added={addedIds.includes(item.id)} pending={addDownloadMutation.isPending && addDownloadMutation.variables?.id === item.id} onDownload={(m) => addDownloadMutation.mutate({ id: m.id, title: m.title, cover: m.cover_url })} />
            ))}
          </SimpleGrid>
        </>
      ) : (
        <>
          <div className="section-header search-section-header">
            <div className="section-header__title-group">
              <span className="section-header__eyebrow">Discovery Feed</span>
              <div className="section-header__headline-row">
                <h2 className="section-header__title">最近更新</h2>
                <span className="section-header__count">{recentItems.length} 项</span>
              </div>
              <div className="section-header__meta-row">
                <span className="section-header__summary">滚动加载最新更新与推荐作品</span>
              </div>
            </div>
            <div className="section-header__actions">
              <ActionIcon className="section-header__refresh" variant="light" color="teal" size="lg" radius="xl" onClick={() => { setRecentPage(1); setRecentHasMore(true); setIsRefreshingRecent(true); void queryClient.invalidateQueries({ queryKey: ["recent-updates"] }); }} loading={recentQuery.isFetching && (recentPage === 1 || isRefreshingRecent)}><IconRefresh /></ActionIcon>
            </div>
          </div>
          <SimpleGrid className="search-page__grid" cols={{ base: 2, sm: 3, md: 4, xl: 5 }} spacing="md">
            {recentItems.map(item => (
              <RecentUpdateCard key={item.id} item={item} added={addedIds.includes(item.id)} pending={addDownloadMutation.isPending && addDownloadMutation.variables?.id === item.id} onDownload={(m) => addDownloadMutation.mutate({ id: m.id, title: m.title, cover: m.cover })} />
            ))}
          </SimpleGrid>
          {recentQuery.isError ? (
            <div className="page-error">{getErrorMessage(recentQuery.error, "最近更新加载失败")}</div>
          ) : null}
          <div ref={recentSentinelRef} style={{ height: 40 }} />
          {recentQuery.isFetching ? (
            <div className="page-empty" style={{ textAlign: "center", marginTop: 16 }}>加载中…</div>
          ) : null}
          {!recentHasMore && !recentQuery.isFetching ? (
            <div className="page-empty" style={{ textAlign: "center", marginTop: 16 }}>没有更多了</div>
          ) : null}
        </>
      )}
    </section>
  );
}
