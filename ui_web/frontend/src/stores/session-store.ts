import { create } from "zustand";

interface SessionPayload {
  username: string;
  loggedIn: boolean;
  rememberPassword: boolean;
  rememberedPassword: string;
}

interface SessionState extends SessionPayload {
  hydrated: boolean;
  setSession(payload: SessionPayload): void;
  markHydrated(): void;
  clear(): void;
}

export const useSessionStore = create<SessionState>((set) => ({
  username: "",
  loggedIn: false,
  rememberPassword: false,
  rememberedPassword: "",
  hydrated: false,
  setSession: (payload) =>
    set({
      ...payload,
      hydrated: true,
    }),
  markHydrated: () =>
    set((state) => ({
      ...state,
      hydrated: true,
    })),
  clear: () =>
    set({
      username: "",
      loggedIn: false,
      rememberPassword: false,
      rememberedPassword: "",
      hydrated: true,
    }),
}));
