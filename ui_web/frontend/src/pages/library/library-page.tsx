import { useMemo, useState, type FormEvent, useEffect, useRef, useCallback } from "react";
import { Button, SegmentedControl, Select, SimpleGrid, TextInput, Group, ActionIcon, Tooltip, Stack } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LibraryItemCard } from "../../components/library-item-card";
import { fetchLibrary, refreshLibrary, repairLibraryMetadata, openLibraryFolder, smartUpdateLibrary } from "../../lib/api/library";
import { addDownload } from "../../lib/api/downloads";
import type { AddDownloadRequest, LibraryItem } from "../../lib/api/contracts";
import { enqueueLibraryItemsInBatches } from "./bulk-library-update";

type SortMode = "title" | "recent";
type SortOrder = "asc" | "desc";
type StatusFilter = "all" | "连载中" | "已完结";

function IconSearch() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.1rem" width="1.1rem"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>; }
function IconSortAsc() { return <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M3 12h18M3 6h10M3 18h6" /></svg>; }
function IconSortDesc() { return <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M3 12h18M3 18h10M3 6h6" /></svg>; }
function IconArrowUp() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M5 15l7-7 7 7" /></svg>; }
function IconArrowDown() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M19 9l-7 7-7-7" /></svg>; }

const PINYIN_BOUNDARIES = [
  { letter: "A", char: "阿" }, { letter: "B", char: "八" }, { letter: "C", char: "擦" }, { letter: "D", char: "搭" }, { letter: "E", char: "蛾" }, { letter: "F", char: "发" }, { letter: "G", char: "旮" }, { letter: "H", char: "哈" }, { letter: "J", char: "击" }, { letter: "K", char: "咔" }, { letter: "L", char: "垃" }, { letter: "M", char: "妈" }, { letter: "N", char: "拿" }, { letter: "O", char: "哦" }, { letter: "P", char: "啪" }, { letter: "Q", char: "期" }, { letter: "R", char: "然" }, { letter: "S", char: "撒" }, { letter: "T", char: "塌" }, { letter: "W", char: "挖" }, { letter: "X", char: "昔" }, { letter: "Y", char: "压" }, { letter: "Z", char: "匝" },
] as const;

function getChineseInitial(char: string): string {
  let current = "A";
  for (const boundary of PINYIN_BOUNDARIES) { if (char.localeCompare(boundary.char, "zh-Hans-CN") >= 0) { current = boundary.letter; continue; } break; }
  return current;
}

function getJumpLetter(title: string): string {
  const text = String(title || "").trim();
  for (const char of text) { if (/\d/.test(char)) return "0-9"; if (/[A-Za-z]/.test(char)) return char.toUpperCase(); if (/[\u4e00-\u9fff]/.test(char)) return getChineseInitial(char); }
  return "";
}

function sortAndFilter(items: LibraryItem[], sort: SortMode, statusFilter: StatusFilter, order: SortOrder): LibraryItem[] {
  let result = items;
  if (statusFilter !== "all") result = result.filter(item => item.status === statusFilter);
  if (sort === "title") {
    result = [...result].sort((a, b) => {
      const cmp = a.title.localeCompare(b.title, "zh-Hans");
      return order === "asc" ? cmp : -cmp;
    });
  } else if (sort === "recent") {
    result = [...result].sort((a, b) => {
      const aTime = a.last_update_ts || a.mtime || 0;
      const bTime = b.last_update_ts || b.mtime || 0;
      return order === "asc" ? aTime - bTime : bTime - aTime;
    });
  }
  return result;
}

export function LibraryPage() {
  const queryClient = useQueryClient();
  const [inputKeyword, setInputKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [feedback, setFeedback] = useState("");
  const [visibleCount, setVisibleCount] = useState(30);
  const [sortMode, setSortMode] = useState<SortMode>("recent");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedLetter, setSelectedLetter] = useState("ALL");
  const [addedIds, setAddedIds] = useState<string[]>([]);
  const [isUpdatingAll, setIsUpdatingAll] = useState(false);
  const [isSmartUpdating, setIsSmartUpdating] = useState(false);

  const loaderRef = useRef<HTMLDivElement>(null);

  const libraryQuery = useQuery({ queryKey: ["library", submittedKeyword], queryFn: () => fetchLibrary(submittedKeyword) });
  
  const refreshMutation = useMutation({
    mutationFn: (keyword: string) => refreshLibrary(keyword),
    onSuccess: (res, keyword) => { 
      queryClient.setQueryData(["library", keyword], res); 
      setFeedback(res.source === "cache" ? `刷新完成，当前仍显示缓存，共 ${res.total} 项` : `已校验磁盘，刷新 ${res.total} 项`);
      setVisibleCount(30); 
    }
  });

  const addDownloadMutation = useMutation({
    mutationFn: (req: AddDownloadRequest) => addDownload(req),
    onSuccess: (res, vars) => { setFeedback(res.message); if (res.ok && vars.id) setAddedIds(prev => [...new Set([...prev, vars.id])]); }
  });

  const repairMutation = useMutation({
    mutationFn: repairLibraryMetadata,
    onSuccess: (res) => {
      const currentKeyword = submittedKeyword;
      setFeedback(res.message);
      refreshMutation.mutate(currentKeyword);
    }
  });

  const isRefreshing = refreshMutation.isPending;
  const isRepairing = repairMutation.isPending;
  const isSingleUpdating = addDownloadMutation.isPending;
  const isBatchUpdating = isUpdatingAll || isSmartUpdating;
  const isWriteBusy = isRefreshing || isRepairing || isSingleUpdating || isBatchUpdating;

  useEffect(() => {
    if (libraryQuery.data?.source === "cache") {
      setFeedback("当前显示缓存，未校验磁盘");
    }
  }, [libraryQuery.data?.source, submittedKeyword]);

  // 无限滚动逻辑
  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const target = entries[0];
    if (target.isIntersecting) {
      setVisibleCount(prev => prev + 30);
    }
  }, []);

  useEffect(() => {
    const option = { root: null, rootMargin: "200px", threshold: 0 };
    const observer = new IntersectionObserver(handleObserver, option);
    if (loaderRef.current) observer.observe(loaderRef.current);
    return () => { if (loaderRef.current) observer.unobserve(loaderRef.current); };
  }, [handleObserver]);

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    if (isWriteBusy) return;
    setFeedback("");
    setVisibleCount(30);
    setSubmittedKeyword(inputKeyword.trim());
  };

  async function handleSmartUpdate() {
    if (isWriteBusy) return;
    setIsSmartUpdating(true);
    try {
      const res = await smartUpdateLibrary();
      const candidates = res.items ?? [];
      if (candidates.length === 0) {
        setFeedback(res.message || "最近更新未命中本地书库或本地已是最新");
        return;
      }

      setFeedback(`智能更新正在加入下载队列：0 / ${candidates.length}`);
      const { stats, addedIds: newlyAddedIds } = await enqueueLibraryItemsInBatches({
        items: candidates,
        enqueue: (item) => addDownload({ id: item.id, title: item.title, cover: item.cover_path }),
        getId: (item) => item.id,
        onProgress: (stats) => {
          setFeedback(`智能更新正在加入下载队列：${stats.processed} / ${stats.total}`);
        },
      });

      setFeedback(
        `智能更新已处理 ${stats.total} 本：新增 ${stats.added}，队列重复 ${stats.duplicated}，失败 ${stats.failed}`,
      );
      setAddedIds(prev => [...new Set([...prev, ...newlyAddedIds])]);
      void queryClient.invalidateQueries({ queryKey: ["downloads", "queue"] });
    } catch {
      setFeedback("智能更新失败，请稍后重试");
    } finally {
      setIsSmartUpdating(false);
    }
  }

  async function handleUpdateAll() {
    if (isWriteBusy || filteredByLetter.length === 0) return;
    setIsUpdatingAll(true);
    setFeedback(`正在加入下载队列：0 / ${filteredByLetter.length}`);
    try {
      const { stats, addedIds: newlyAddedIds } = await enqueueLibraryItemsInBatches({
        items: filteredByLetter,
        enqueue: (item) => addDownload({ id: item.id, title: item.title, cover: item.cover_path }),
        getId: (item) => item.id,
        onProgress: (stats) => {
          setFeedback(`正在加入下载队列：${stats.processed} / ${stats.total}`);
        },
      });
      setFeedback(`已处理 ${stats.total} 本：新增 ${stats.added}，队列重复 ${stats.duplicated}，失败 ${stats.failed}`);
      setAddedIds(prev => [...new Set([...prev, ...newlyAddedIds])]);
      void queryClient.invalidateQueries({ queryKey: ["downloads", "queue"] });
    } finally { setIsUpdatingAll(false); }
  }

  const rawItems = libraryQuery.data?.items ?? [];
  const processedItems = useMemo(() => sortAndFilter(rawItems, sortMode, statusFilter, sortOrder), [rawItems, sortMode, statusFilter, sortOrder]);
  const letters = useMemo(() => { const arr = ["ALL", "0-9"]; for (let i = 65; i <= 90; i++) arr.push(String.fromCharCode(i)); return arr; }, []);
  const letterCounts = useMemo(() => { const counts: Record<string, number> = {}; for (const i of processedItems) { const l = getJumpLetter(i.title); if (l) counts[l] = (counts[l] || 0) + 1; } return counts; }, [processedItems]);
  const filteredByLetter = useMemo(() => selectedLetter === "ALL" ? processedItems : processedItems.filter(i => getJumpLetter(i.title) === selectedLetter), [processedItems, selectedLetter]);
  const visibleItems = filteredByLetter.slice(0, visibleCount);
  const statusCounts = useMemo(() => { const counts = { all: rawItems.length, "连载中": 0, "已完结": 0 }; for (const i of rawItems) { if (i.status === "连载中") counts["连载中"]++; else if (i.status === "已完结") counts["已完结"]++; } return counts; }, [rawItems]);

  return (
    <section className="page-container">
      <Stack gap="lg">
        <div className="library-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Group gap="md">
            <h2 style={{ margin: 0 }}>本地书库</h2>
            <span className="library-header__count" style={{ opacity: 0.6, fontSize: "0.9rem" }}>{rawItems.length} 本作品</span>
          </Group>
          <Group gap="xs">
            <Button variant="light" color="teal" size="compact-sm" onClick={() => refreshMutation.mutate(submittedKeyword)} loading={isRefreshing} disabled={isWriteBusy}>刷新</Button>
            <Button variant="light" color="teal" size="compact-sm" onClick={() => repairMutation.mutate()} loading={isRepairing} disabled={isWriteBusy}>补全</Button>
            <Button variant="light" color="teal" size="compact-sm" onClick={handleSmartUpdate} disabled={isWriteBusy} loading={isSmartUpdating}>智能更新</Button>
            <Button variant="light" color="teal" size="compact-sm" onClick={handleUpdateAll} disabled={filteredByLetter.length === 0 || isWriteBusy} loading={isUpdatingAll}>全量更新 ({filteredByLetter.length})</Button>
          </Group>
        </div>

        <Stack gap="md">
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
            <form className="search-bar-wrap" style={{ flex: 1, maxWidth: 300, background: "rgba(0,0,0,0.05)", borderRadius: 8 }} onSubmit={handleSearch}>
              <TextInput variant="unstyled" px="md" style={{ flex: 1 }} placeholder="搜索库中作品..." value={inputKeyword} onChange={(e) => setInputKeyword(e.target.value)} leftSection={<IconSearch />} />
            </form>
            <Group gap="sm">
              <SegmentedControl size="sm" radius="xl" value={statusFilter} onChange={(v) => { setStatusFilter(v as StatusFilter); setVisibleCount(30); }} data={[{ label: `全部 (${statusCounts.all})`, value: "all" }, { label: "连载", value: "连载中" }, { label: "完结", value: "已完结" }]} />
              <Group gap={4}>
                <Select size="sm" radius="md" style={{ width: 110 }} value={sortMode} onChange={(v) => { setSortMode(v as SortMode); setVisibleCount(30); }} data={[{ label: "名称", value: "title" }, { label: "更新时间", value: "recent" }]} />
                <Tooltip label={sortOrder === "asc" ? "正序" : "倒序"}>
                  <ActionIcon variant="light" color="gray" size="lg" radius="md" onClick={() => { setSortOrder(o => o === "asc" ? "desc" : "asc"); setVisibleCount(30); }}>
                    {sortOrder === "asc" ? <IconArrowUp /> : <IconArrowDown />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          </div>
          
          <div className="letter-filter-bar" style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {letters.map(l => { 
              const count = l === "ALL" ? processedItems.length : letterCounts[l] || 0; 
              return (
                <button 
                  key={l} 
                  className={`letter-filter-btn ${selectedLetter === l ? "active" : ""} ${count === 0 ? "empty" : ""}`} 
                  onClick={() => { setSelectedLetter(l); setVisibleCount(30); }} 
                  title={`${l}: ${count} 本`}
                  style={{ 
                    padding: "2px 8px", 
                    fontSize: "0.8rem", 
                    borderRadius: 4, 
                    border: "none",
                    cursor: count > 0 || l === "ALL" ? "pointer" : "default",
                    background: selectedLetter === l ? "var(--mantine-color-teal-light)" : "transparent",
                    color: selectedLetter === l ? "var(--mantine-color-teal-filled)" : (count === 0 ? "#ccc" : "inherit")
                  }}
                >
                  {l}
                </button>
              ); 
            })}
          </div>
        </Stack>

        {feedback && <div className="page-feedback" style={{ padding: "8px 12px", background: "rgba(20, 184, 166, 0.1)", color: "#0d9488", borderRadius: 6, fontSize: "0.9rem" }}>{feedback}</div>}
        
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4, xl: 5 }} spacing="md">
          {visibleItems.map(item => (
            <LibraryItemCard
              key={item.path}
              item={item}
              added={addedIds.includes(item.id)}
              pending={isSingleUpdating ? addDownloadMutation.variables?.id === item.id : isWriteBusy}
              onUpdate={(m) => {
                if (isWriteBusy) return;
                addDownloadMutation.mutate({ id: m.id, title: m.title, cover: m.cover_path });
              }}
              onOpenFolder={(m) => openLibraryFolder(m.path)}
            />
          ))}
        </SimpleGrid>
        
        {/* 加载更多触发点 */}
        <div ref={loaderRef} style={{ height: 40, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0.5, fontSize: "0.9rem" }}>
          {visibleItems.length < filteredByLetter.length ? "正在加载更多..." : (filteredByLetter.length > 0 ? "已加载全部作品" : "")}
        </div>
      </Stack>
    </section>
  );
}
