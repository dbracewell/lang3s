"use client";

import { Provider as JotaiProvider } from "jotai";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { TRPCReactProvider } from "@/lib/trpc/client";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { SSEProvider } from "@/lib/events/SSEProvider";
import { Toaster } from "@/components/ui/sonner";
import React from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <JotaiProvider>
        <TRPCReactProvider>
          <NuqsAdapter>
            <SSEProvider>{children}</SSEProvider>
          </NuqsAdapter>
        </TRPCReactProvider>
      </JotaiProvider>
      <Toaster richColors position="top-center" />
    </ThemeProvider>
  );
}
