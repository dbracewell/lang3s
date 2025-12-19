"use client";

import React, { useEffect } from "react";
import { initRealtime } from "@/lib/events/realtime";

export function SSEProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    initRealtime();
  }, []);

  return <>{children}</>;
}
