import { useEffect, useState } from "react";
import { Button, TextInput, NumberInput, Stack, Group, Text, Badge, Divider, Alert } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCrawlerStatus, startCrawler, stopCrawler } from "../../lib/api/crawler";
import { fetchSettings, updateSettings } from "../../lib/api/settings";
import type { CrawlerStatus, SettingsUpdateRequest } from "../../lib/api/contracts";
import { connectEvents } from "../../lib/ws/events";

function isCrawlerStatus(payload: any): payload is CrawlerStatus { return payload && typeof payload === "object" && "running" in payload; }

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [maxBooks, setMaxBooks] = useState<number | string>(1);
  const [maxImages, setMaxImages] = useState<number | string>(5);
  const [downloadDir, setDownloadDir] = useState("");
  const [startId, setStartId] = useState("1");
  const [endId, setEndId] = useState("1");
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus | null>(null);
  const [feedback, setFeedback] = useState("");
  const [crawlerError, setCrawlerError] = useState("");

  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const updateMutation = useMutation({
    mutationFn: (req: SettingsUpdateRequest) => updateSettings(req),
    onSuccess: () => { setFeedback("设置已成功保存"); void queryClient.invalidateQueries({ queryKey: ["settings"] }); }
  });

  const crawlerQuery = useQuery({ queryKey: ["crawler", "status"], queryFn: fetchCrawlerStatus, refetchInterval: 2000 });
  const startMutation = useMutation({
    mutationFn: (a: { start_id: number; end_id: number }) => startCrawler(a),
    onSuccess: (d) => {
      setCrawlerError("");
      setCrawlerStatus(d);
    },
    onError: (error: unknown) => {
      setCrawlerError(error instanceof Error ? error.message : "启动索引更新失败");
    },
  });
  const stopMutation = useMutation({
    mutationFn: stopCrawler,
    onSuccess: (d) => {
      setCrawlerError("");
      setCrawlerStatus({ running: false, last_message: d.message, max_known_id: crawlerStatus?.max_known_id || 0 });
    },
  });

  useEffect(() => {
    if (settingsQuery.data) {
      setMaxBooks(settingsQuery.data.max_books);
      setMaxImages(settingsQuery.data.max_images);
      setDownloadDir(settingsQuery.data.download_dir);
    }
  }, [settingsQuery.data]);

  useEffect(() => {
    if (crawlerQuery.data) {
      setCrawlerStatus(crawlerQuery.data);
      const mid = crawlerQuery.data.max_known_id || 1;
      setStartId(String(mid));
      setEndId(String(mid + 1000));
    }
  }, [crawlerQuery.data]);

  useEffect(() => {
    const socket = connectEvents((e) => {
      if (e.type === "crawler.progress" && isCrawlerStatus(e.payload)) {
        setCrawlerError("");
        setCrawlerStatus(e.payload);
        const mid = e.payload.max_known_id || 1;
        setStartId(String(mid));
        setEndId(String(mid + 1000));
      }
    }, { onReconnect() { void queryClient.invalidateQueries({ queryKey: ["crawler", "status"] }); } });
    return () => socket.close();
  }, [queryClient]);

  return (
    <section className="page-container">
      <div className="library-header" style={{ marginBottom: 32 }}>
        <div className="library-header__title"><h2>设置与工具</h2><span className="library-header__count">管理应用行为与数据索引</span></div>
      </div>

      {feedback && <Alert color="teal" variant="light" mb="xl" withCloseButton onClose={() => setFeedback("")}>{feedback}</Alert>}
      {crawlerError && <Alert color="red" variant="light" mb="xl" withCloseButton onClose={() => setCrawlerError("")}>{crawlerError}</Alert>}

      <Stack gap="xl">
        <div className="settings-group">
          <Text fw={800} mb="lg" color="var(--accent)" size="xl">通用设置</Text>
          <Stack gap="md">
            <TextInput label="书库下载路径" description="漫画文件存储的物理位置（绝对路径）" value={downloadDir} onChange={(e) => setDownloadDir(e.target.value)} radius="md" />
            <Group grow align="flex-start">
              <NumberInput label="并行下载书籍数" value={maxBooks} onChange={setMaxBooks} min={1} max={10} radius="md" />
              <NumberInput label="单本并行图片数" value={maxImages} onChange={setMaxImages} min={1} max={32} radius="md" />
            </Group>
            <Button mt="md" color="teal" size="md" onClick={() => updateMutation.mutate({ max_books: Number(maxBooks), max_images: Number(maxImages), download_dir: downloadDir })} loading={updateMutation.isPending}>保存通用设置</Button>
          </Stack>
        </div>

        <div className="settings-group">
          <Text fw={800} mb="lg" color="var(--accent)" size="xl">索引工具</Text>
          <Group align="flex-start" gap="xl">
            <Stack style={{ flex: 1 }}>
              <TextInput label="起始 ID" value={startId} onChange={(e) => setStartId(e.target.value)} radius="md" />
              <TextInput label="终止 ID" value={endId} onChange={(e) => setEndId(e.target.value)} radius="md" />
              <Group grow>
                <Button color="teal" onClick={() => startMutation.mutate({ start_id: Number(startId), end_id: Number(endId) })} disabled={crawlerStatus?.running} loading={startMutation.isPending}>启动索引更新</Button>
                <Button variant="light" color="red" onClick={() => stopMutation.mutate()} disabled={!crawlerStatus?.running} loading={stopMutation.isPending}>停止</Button>
              </Group>
            </Stack>
            <div className="crawler-status-box" style={{ flex: 1 }}>
              <Text fw={700} size="sm" mb="md" opacity={0.6}>实时状态监控</Text>
              <Stack gap="xs">
                <Group justify="space-between"><Text size="sm">工作状态</Text><Badge color={crawlerStatus?.running ? "teal" : "gray"}>{crawlerStatus?.running ? "正在运行" : "空闲"}</Badge></Group>
                <Group justify="space-between"><Text size="sm">最大 ID</Text><Text size="sm" fw={700}>{crawlerStatus?.max_known_id || "未知"}</Text></Group>
                <Divider my="xs" variant="dashed" />
                <Text size="xs" opacity={0.5}>最新进度消息</Text>
                <Text size="xs" fw={600} style={{ wordBreak: "break-all" }}>{crawlerStatus?.last_message || "暂无消息"}</Text>
              </Stack>
            </div>
          </Group>
        </div>
      </Stack>
    </section>
  );
}
