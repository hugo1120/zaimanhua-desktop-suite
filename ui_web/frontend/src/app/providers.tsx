import type { PropsWithChildren } from "react";
import { MantineProvider, localStorageColorSchemeManager } from "@mantine/core";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./query-client";

const colorSchemeManager = localStorageColorSchemeManager({
  key: "zaimanhua-color-scheme",
});

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <MantineProvider colorSchemeManager={colorSchemeManager} defaultColorScheme="dark">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MantineProvider>
  );
}
