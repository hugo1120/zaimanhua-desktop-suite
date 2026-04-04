import { create } from "zustand";

import type { DownloadTaskItem } from "../lib/api/contracts";

interface DownloadsState {
  active: DownloadTaskItem[];
  waiting: DownloadTaskItem[];
  replaceQueue(payload: { active: DownloadTaskItem[]; waiting: DownloadTaskItem[] }): void;
  upsertTask(task: DownloadTaskItem): void;
  removeTask(taskId: string): void;
}

function withoutTask(tasks: DownloadTaskItem[], taskId: string) {
  return tasks.filter((task) => task.id !== taskId);
}

export const useDownloadsStore = create<DownloadsState>((set) => ({
  active: [],
  waiting: [],
  replaceQueue: (payload) =>
    set({
      active: payload.active,
      waiting: payload.waiting,
    }),
  upsertTask: (task) =>
    set((state) => {
      const nextActive = withoutTask(state.active, task.id);
      const nextWaiting = withoutTask(state.waiting, task.id);

      if (task.status === "waiting") {
        return {
          active: nextActive,
          waiting: [task, ...nextWaiting],
        };
      }

      return {
        active: [task, ...nextActive],
        waiting: nextWaiting,
      };
    }),
  removeTask: (taskId) =>
    set((state) => ({
      active: withoutTask(state.active, taskId),
      waiting: withoutTask(state.waiting, taskId),
    })),
}));
