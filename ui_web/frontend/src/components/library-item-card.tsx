import { ActionIcon, Button, Card, Image, Text, Tooltip } from "@mantine/core";

import type { LibraryItem } from "../lib/api/contracts";
import { fetchMangaDetail } from "../lib/api/manga";
import { MangaDescriptionHover } from "./manga-description-hover";

function libraryCoverSrc(item: LibraryItem): string | undefined {
  if (!item.cover_path) return undefined;
  // 稳健提取目录名和文件名
  const parts = item.path.replace(/\\/g, "/").split("/").filter(Boolean);
  const folderName = parts[parts.length - 1] || "";
  const coverParts = item.cover_path.replace(/\\/g, "/").split("/").filter(Boolean);
  const coverFile = coverParts[coverParts.length - 1] || "";
  
  if (!folderName || !coverFile) return undefined;
  return `/api/covers?path=${encodeURIComponent(folderName + "/" + coverFile)}`;
}

function IconFolder() {
  return (
    <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" height="1.1rem" width="1.1rem">
      <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  );
}

export function LibraryItemCard(props: {
  item: LibraryItem;
  pending?: boolean;
  added?: boolean;
  onUpdate(item: LibraryItem): void;
  onOpenFolder?(item: LibraryItem): void;
}) {
  const { item, pending = false, added = false, onUpdate, onOpenFolder } = props;

  return (
    <Card className="poster-card" padding={0} radius="md">
      <div className="poster-card__cover">
        <Image
          src={libraryCoverSrc(item)}
          alt={item.title}
          fit="cover"
          h="100%"
          w="100%"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='280'%3E%3Crect fill='%23262630' width='200' height='280'/%3E%3Ctext x='50%25' y='50%25' fill='%23555' font-size='36' text-anchor='middle' dy='.35em'%3E📖%3C/text%3E%3C/svg%3E"
        />
        <div className="poster-card__overlay">
          <div style={{ display: "flex", gap: 8, padding: "0 4px" }}>
            <Button
              size="xs"
              style={{ flex: 1 }}
              loading={pending}
              color={added ? "teal" : "teal"}
              variant="filled"
              disabled={added}
              onClick={(e) => { e.stopPropagation(); onUpdate(item); }}
            >
              {added ? "已加入" : "更新"}
            </Button>
            {onOpenFolder ? (
              <Tooltip label="打开本地目录" position="top">
                <ActionIcon
                  variant="filled"
                  color="teal"
                  size="md"
                  radius="sm"
                  onClick={(e) => { e.stopPropagation(); onOpenFolder(item); }}
                >
                  <IconFolder />
                </ActionIcon>
              </Tooltip>
            ) : null}
          </div>
        </div>
        {item.status ? (
          <span className={`poster-card__badge ${item.status === "已完结" ? "poster-card__badge--done" : ""}`}>
            {item.status}
          </span>
        ) : null}
      </div>
      <div className="poster-card__info">
        <MangaDescriptionHover
          id={item.id}
          title={item.title}
          description={item.description}
          detailApi={fetchMangaDetail}
        />
        <div className="poster-card__meta">
          <Text className="poster-card__meta-left" c="dimmed" span>
            {item.author || "未知作者"}
          </Text>
        </div>
      </div>
    </Card>
  );
}
