"use client";

import { Provider as JotaiProvider } from "jotai";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "@/components/ui/sonner";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { eventRouter } from "@/lib/events/eventRouter";

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
          <NuqsAdapter>
            <EventProvider>{children}</EventProvider>
          </NuqsAdapter>
        </QueryClientProvider>
      </JotaiProvider>
      <Toaster richColors position="top-center" closeButton duration={3000} />
    </ThemeProvider>
  );
}

const EventProvider = ({ children }: { children: React.ReactNode }) => {
  React.useEffect(() => {
    const eventSource = new EventSource("/api/realtime");
    eventSource.onmessage = (event) => {
      try {
        eventRouter(event.data);
      } catch (err) {
        console.error(err);
      }
    };
    eventSource.addEventListener("connected", () => {
      // connection established
    });
    eventSource.onerror = (error) => {
      eventSource.close();
    };
    return () => {
      eventSource.close();
    };
  }, []);

  return children;
};
