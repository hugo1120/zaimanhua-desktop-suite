import { HoverCard, Loader, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { MangaDetail } from "../lib/api/contracts";

export function MangaDescriptionHover(props: {
  id: string;
  title: string;
  description?: string;
  detailApi(id: string): Promise<MangaDetail>;
}) {
  const { id, title, description = "", detailApi } = props;
  const [opened, setOpened] = useState(false);

  const detailQuery = useQuery({
    queryKey: ["manga-detail", id],
    queryFn: () => detailApi(id),
    enabled: opened && !description,
    staleTime: 5 * 60 * 1000,
  });

  const detailText = description || detailQuery.data?.description || "";

  return (
    <HoverCard
      width={280}
      shadow="md"
      openDelay={150}
      withinPortal
      onOpen={() => setOpened(true)}
    >
      <HoverCard.Target>
        <Text className="poster-card__title" size="sm" fw={600} lineClamp={2}>
          {title}
        </Text>
      </HoverCard.Target>
      <HoverCard.Dropdown>
        {detailQuery.isFetching && !detailText ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 8 }}>
            <Loader size="sm" />
          </div>
        ) : (
          <Text size="sm" c={detailText ? undefined : "dimmed"}>
            {detailText || "暂无简介"}
          </Text>
        )}
      </HoverCard.Dropdown>
    </HoverCard>
  );
}
