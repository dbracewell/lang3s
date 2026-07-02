"use client";

import { Provider as JotaiProvider } from "jotai";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "@/components/ui/sonner";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    mutations: {
      onSuccess: async () => {
        await queryClient.invalidateQueries();
      },
    },
  },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <JotaiProvider>
        <QueryClientProvider client={queryClient}>
          <NuqsAdapter>{children}</NuqsAdapter>
        </QueryClientProvider>
      </JotaiProvider>
      <Toaster richColors position="top-center" />
    </ThemeProvider>
  );
}
