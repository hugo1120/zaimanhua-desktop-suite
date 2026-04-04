import { useEffect, useRef, useState } from "react";
import { Group, Stack, Text, Badge, Paper, Button } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DownloadTaskRow } from "../../components/download-task-row";
import { cancelDownload, fetchDownloadQueue, stopAllDownloads } from "../../lib/api/downloads";
import type { DownloadTaskItem } from "../../lib/api/contracts";
import { connectEvents } from "../../lib/ws/events";
import { useDownloadsStore } from "../../stores/downloads-store";
import {
  createQueueRefreshScheduler,
  formatStopAllSummaryMessage,
  isStopAllSummaryPayload,
} from "./queue-refresh";

function isDownloadTaskPayload(payload: unknown): payload is DownloadTaskItem {
  return Boolean(payload) && typeof payload === "object" && typeof (payload as { id?: unknown }).id === "string";
}

function IconStop() { return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1rem" width="1rem"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>; }
function IconEmptyBox() { return <svg fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" height="3rem" width="3rem" style={{ opacity: 0.3, marginBottom: '1rem' }}><path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" /></svg>; }

export function DownloadsPage() {
  const queryClient = useQueryClient();
  const active = useDownloadsStore(state => state.active);
  const waiting = useDownloadsStore(state => state.waiting);
  const replaceQueue = useDownloadsStore(state => state.replaceQueue);
  const upsertTask = useDownloadsStore(state => state.upsertTask);
  const removeTask = useDownloadsStore(state => state.removeTask);
  const [feedback, setFeedback] = useState("");
  const [isStopAllSubmitting, setIsStopAllSubmitting] = useState(false);
  const queueRefreshSchedulerRef = useRef<ReturnType<typeof createQueueRefreshScheduler> | null>(null);

  const queueQuery = useQuery({ queryKey: ["downloads", "queue"], queryFn: fetchDownloadQueue });

  if (queueRefreshSchedulerRef.current === null) {
    queueRefreshSchedulerRef.current = createQueueRefreshScheduler(() => {
      void queryClient.invalidateQueries({ queryKey: ["downloads", "queue"] });
    });
  }

  useEffect(() => { if (queueQuery.data) replaceQueue(queueQuery.data); }, [queueQuery.data, replaceQueue]);

  useEffect(() => {
    return () => {
      queueRefreshSchedulerRef.current?.cancel();
    };
  }, []);

  useEffect(() => {
    const socket = connectEvents((event) => {
      if (event.type === "queue.changed") {
        queueRefreshSchedulerRef.current?.schedule();
        return;
      }

      if (event.type === "download.stop_all") {
        if (isStopAllSummaryPayload(event.payload)) {
          setFeedback(formatStopAllSummaryMessage(event.payload));
        }
        queueRefreshSchedulerRef.current?.schedule();
        return;
      }

      if (!isDownloadTaskPayload(event.payload)) return;
      if (event.type === "download.task_finished" || event.type === "download.task_failed" || event.type === "download.task_canceled") { removeTask(event.payload.id); }
      else if (event.type === "download.task_added" || event.type === "download.task_updated") { upsertTask(event.payload); }
    }, { onReconnect() { queueRefreshSchedulerRef.current?.schedule(); } });
    return () => socket.close();
  }, [removeTask, upsertTask]);

  async function handleCancel(taskId: string) {
    await cancelDownload(taskId);
    queueRefreshSchedulerRef.current?.schedule();
  }

  async function handleStopAll() {
    setIsStopAllSubmitting(true);
    try {
      const response = await stopAllDownloads();
      setFeedback(response.message);
      queueRefreshSchedulerRef.current?.schedule();
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "停止全部失败");
    } finally {
      setIsStopAllSubmitting(false);
    }
  }

  const totalCount = active.length + waiting.length;

  return (
    <section className="page-container">
      <Group justify="space-between" align="center" mb="xl">
        <Group gap="md">
          <h2 style={{ margin: 0, fontSize: 28, fontWeight: 800 }}>下载中心</h2>
          <Badge variant="light" color="teal" size="xl" radius="md">{totalCount} 个任务</Badge>
        </Group>
        <Button variant="light" color="red" size="md" radius="md" leftSection={<IconStop />} onClick={handleStopAll} disabled={totalCount === 0 || isStopAllSubmitting} loading={isStopAllSubmitting}>
          停止全部
        </Button>
      </Group>

      <Stack gap="xl">
        {feedback ? (
          <Paper p="sm" radius="md" style={{ background: "rgba(20, 184, 166, 0.08)" }}>
            <Text size="sm" c="teal.3" fw={600}>{feedback}</Text>
          </Paper>
        ) : null}

        <div className="task-section">
          <div className="section-header" style={{ marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800, opacity: 0.8 }}>活跃中 ({active.length})</h2>
          </div>
          {active.length > 0 ? (
            active.map(task => <DownloadTaskRow key={task.id} task={task} onCancel={handleCancel} />)
          ) : (
            <Paper p="xl" radius="lg" style={{ background: "rgba(255,255,255,0.03)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200 }}>
              <IconEmptyBox />
              <Text c="dimmed" fw={600} size="md">暂无活跃任务</Text>
            </Paper>
          )}
        </div>

        <div className="task-section">
          <div className="section-header" style={{ marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800, opacity: 0.8 }}>等待队列 ({waiting.length})</h2>
          </div>
          {waiting.length > 0 ? (
            waiting.map(task => <DownloadTaskRow key={task.id} task={task} onCancel={handleCancel} />)
          ) : (
            <Paper p="xl" radius="lg" style={{ background: "rgba(255,255,255,0.03)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200 }}>
              <IconEmptyBox />
              <Text c="dimmed" fw={600} size="md">队列已空</Text>
            </Paper>
          )}
        </div>
      </Stack>
    </section>
  );
}
