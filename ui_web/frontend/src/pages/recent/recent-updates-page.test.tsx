import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { AppProviders } from "../../app/providers";
import { RecentUpdatesPage } from "./recent-updates-page";

describe("RecentUpdatesPage", () => {
  test("changes page and keeps cards visible", async () => {
    const user = userEvent.setup();
    const listPage = vi
      .fn()
      .mockResolvedValueOnce({
        page: 1,
        items: [{ id: "10", title: "第一页", cover: "", author: "A", status: "连载中", latest: "第1话", time: "今天" }],
      })
      .mockResolvedValueOnce({
        page: 2,
        items: [{ id: "11", title: "第二页", cover: "", author: "B", status: "连载中", latest: "第2话", time: "今天" }],
      });

    render(
      <AppProviders>
        <RecentUpdatesPage listPageApi={listPage} />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("第一页")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      expect(screen.getByText("第二页")).toBeInTheDocument();
    });
  });

  test("shows recent update status and time", async () => {
    const listPage = vi.fn().mockResolvedValueOnce({
      page: 1,
      items: [
        {
          id: "10",
          title: "第一页",
          cover: "",
          author: "A",
          status: "已完结",
          latest: "第1话",
          time: "2026-04-05 12:00",
        },
      ],
    });

    render(
      <AppProviders>
        <RecentUpdatesPage listPageApi={listPage} />
      </AppProviders>,
    );

    await waitFor(() => {
      expect(screen.getByText("第一页")).toBeInTheDocument();
    });

    expect(screen.getByText("已完结")).toBeInTheDocument();
    expect(screen.getByText("2026-04-05 12:00")).toBeInTheDocument();
  });
});
