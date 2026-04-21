import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { AppProviders } from "../app/providers";
import { SearchResultCard } from "./search-result-card";
import * as mangaApi from "../lib/api/manga";

vi.mock("../lib/api/manga", () => ({
  fetchMangaDetail: vi.fn(),
}));

describe("SearchResultCard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test("uses detail author when search item author is missing", async () => {
    (mangaApi.fetchMangaDetail as any).mockResolvedValue({
      id: "123",
      title: "网页搜索结果",
      description: "补全简介",
      author: "详情作者",
      status: "连载中",
      cover_url: "",
    });

    render(
      <AppProviders>
        <SearchResultCard
          item={{
            id: "123",
            title: "网页搜索结果",
            author: "",
            source: "web",
            status: "",
            cover_url: "",
            description: "",
          }}
          onDownload={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("详情作者")).toBeInTheDocument();
    });

    expect(screen.queryByText("未知作者")).not.toBeInTheDocument();
  });

  test("requests detail when only author is missing", async () => {
    (mangaApi.fetchMangaDetail as any).mockResolvedValue({
      id: "456",
      title: "保留已有信息",
      description: "已有简介",
      author: "详情作者二",
      status: "连载中",
      cover_url: "https://example.com/cover.jpg",
    });

    render(
      <AppProviders>
        <SearchResultCard
          item={{
            id: "456",
            title: "保留已有信息",
            author: "",
            source: "web",
            status: "连载中",
            cover_url: "https://example.com/cover.jpg",
            description: "已有简介",
          }}
          onDownload={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(mangaApi.fetchMangaDetail).toHaveBeenCalledWith("456");
      expect(screen.getByText("详情作者二")).toBeInTheDocument();
    });
  });
});
