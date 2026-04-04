import { Button, Card, Image, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";

import { fetchMangaDetail } from "../lib/api/manga";
import type { SearchItem } from "../lib/api/contracts";
import { MangaDescriptionHover } from "./manga-description-hover";

export function SearchResultCard(props: {
  item: SearchItem;
  pending?: boolean;
  added?: boolean;
  onDownload(item: SearchItem): void;
}) {
  const { item, onDownload, pending = false, added = false } = props;
  const detailQuery = useQuery({
    queryKey: ["manga-detail", item.id],
    queryFn: () => fetchMangaDetail(item.id),
    enabled: !item.cover_url || !item.description || !item.status,
    staleTime: 5 * 60 * 1000,
  });
  const resolvedCover = item.cover_url || detailQuery.data?.cover_url || undefined;
  const resolvedDescription = item.description || detailQuery.data?.description || "";
  const resolvedStatus = item.status || detailQuery.data?.status || "";
  const resolvedSource = item.source.replaceAll("+", " + ");

  return (
    <Card className="poster-card" padding={0} radius="md">
      <div className="poster-card__cover">
        <Image
          src={resolvedCover}
          alt={item.title}
          fit="cover"
          h="100%"
          w="100%"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='280'%3E%3Crect fill='%23262630' width='200' height='280'/%3E%3Ctext x='50%25' y='50%25' fill='%23555' font-size='36' text-anchor='middle' dy='.35em'%3E📖%3C/text%3E%3C/svg%3E"
        />
        <div className="poster-card__overlay">
          <Button
            size="xs"
            fullWidth
            loading={pending}
            color="teal"
            variant="filled"
            disabled={added}
            onClick={(e) => { e.stopPropagation(); onDownload(item); }}
          >
            {added ? "已加入" : "下载"}
          </Button>
        </div>
        {resolvedStatus ? (
          <span className={`poster-card__badge ${resolvedStatus === "已完结" ? "poster-card__badge--done" : ""}`}>
            {resolvedStatus}
          </span>
        ) : null}
      </div>
      <div className="poster-card__info">
        <MangaDescriptionHover
          id={item.id}
          title={item.title}
          description={resolvedDescription}
          detailApi={fetchMangaDetail}
        />
        <div className="poster-card__meta">
          <Text className="poster-card__meta-left" c="dimmed" span>
            {item.author || "未知作者"}
          </Text>
          {resolvedSource ? (
            <Text className="poster-card__meta-right" c="dimmed" span>
              {resolvedSource}
            </Text>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
