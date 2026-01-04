"use client";

import { useEffect } from "react";
import { useSetAtom } from "jotai";
import { eventBus } from "@/lib/events/eventBus";
import { toast } from "sonner";
import { upsertAgentStatus } from "@/features/events/stores/agent";

export function AgentStatusUpdateListener() {
  const upsert = useSetAtom(upsertAgentStatus);

  useEffect(() => {
    return eventBus.on("agent:update", (event) => {
      if (event.progress === 100) {
        toast.success(`Agent has answered your prompt ${event.prompt} `);
      }
      upsert({
        id: event.id,
        prompt: event.prompt,
        progress: event.progress,
        response: event.response,
      });
    });
  }, [upsert]);

  return null;
}
