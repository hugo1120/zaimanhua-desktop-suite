import { Button, Card, Image, Text } from "@mantine/core";

import { fetchMangaDetail } from "../lib/api/manga";
import type { RecentUpdateItem } from "../lib/api/contracts";
import { MangaDescriptionHover } from "./manga-description-hover";

export function RecentUpdateCard(props: {
  item: RecentUpdateItem;
  pending?: boolean;
  added?: boolean;
  onDownload(item: RecentUpdateItem): void;
}) {
  const { item, pending = false, added = false, onDownload } = props;

  return (
    <Card className="poster-card" padding={0} radius="md">
      <div className="poster-card__cover">
        <Image
          src={item.cover || undefined}
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
        {item.latest ? <span className="poster-card__badge">{item.latest}</span> : null}
      </div>
      <div className="poster-card__info">
        <MangaDescriptionHover
          id={item.id}
          title={item.title}
          detailApi={fetchMangaDetail}
        />
        <div className="poster-card__meta">
          <Text className="poster-card__meta-left" c="dimmed" span>
            {item.author || "未知作者"}
          </Text>
          {item.time ? (
            <Text className="poster-card__meta-right" c="dimmed" span>
              {item.time}
            </Text>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
