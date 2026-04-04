import { ActionIcon, Progress, Tooltip, Image, Text, Group, Badge } from "@mantine/core";
import { useMemo } from "react";
import type { DownloadTaskItem } from "../lib/api/contracts";

interface DownloadTaskRowProps {
  task: DownloadTaskItem;
  onCancel(id: string): void;
}

function IconCancel() {
  return <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" height="1.2rem" width="1.2rem"><path d="M6 18L18 6M6 6l12 12" /></svg>;
}

export function DownloadTaskRow({ task, onCancel }: DownloadTaskRowProps) {
  const isCanceled = task.status === "canceled" || task.status === "stopping";
  const isError = task.status === "error";
  const isFinished = task.status === "finished";
  const isWaiting = task.status === "waiting";

  const coverUrl = useMemo(() => {
    if (!task.cover) return "";
    if (task.cover.startsWith("http")) return task.cover;
    try {
      const normalized = task.cover.replace(/\\/g, "/");
      const parts = normalized.split("/").filter(Boolean);
      if (parts.length >= 2) {
        const fileName = parts.pop();
        const folderName = parts.pop();
        return `/api/covers?path=${encodeURIComponent(folderName + "/" + fileName)}`;
      }
      return `/api/covers?path=${encodeURIComponent(normalized)}`;
    } catch (e) { return ""; }
  }, [task.cover]);

  return (
    <div className="download-task">
      <div className="download-task__thumbnail">
        <Image src={coverUrl || undefined} alt={task.title} fit="cover" h="100%" referrerPolicy="no-referrer" fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='64'%3E%3Crect fill='%23262630' width='48' height='64'/%3E%3Ctext x='50%25' y='55%25' fill='%23555' font-size='24' text-anchor='middle'%3E📖%3C/text%3E%3C/svg%3E" />
      </div>

      <div className="download-task__content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div>
            <Text fw={700} size="md" lineClamp={1}>{task.title}</Text>
            <Badge variant="light" color={isError ? "red" : isFinished ? "teal" : "teal"} size="xs" mt={4}>
              {isWaiting ? "排队中" : isFinished ? "完成" : isError ? "失败" : task.message || "下载中"}
            </Badge>
          </div>
          {!isFinished && !isCanceled && (
            <ActionIcon variant="light" color="red" radius="md" onClick={() => onCancel(task.id)} title="取消任务"><IconCancel /></ActionIcon>
          )}
        </div>

        <div style={{ flex: 1, marginTop: 'auto' }}>
            <Progress value={task.progress * 100} size="sm" radius="xl" striped animated={task.status === "downloading"} color="teal" />
            {task.total_chapters > 0 && (
              <Text size="xs" c="dimmed" mt={4} fw={600}>进度: {task.done_chapters} / {task.total_chapters} 章节</Text>
            )}
        </div>
      </div>
    </div>
  );
}
