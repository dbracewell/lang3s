"use client";

import { useEffect } from "react";
import { useSetAtom } from "jotai";
import { eventBus } from "@/lib/events/eventBus";
import { toast } from "sonner";
import { upsertJobStatusAtom } from "@/features/events/stores/job-stores";

export function JobStatusListener() {
  const upsert = useSetAtom(upsertJobStatusAtom);

  useEffect(() => {
    return eventBus.on("job:update", (event) => {
      console.log("EVENT BUS", event);
      if (event.status === "completed") {
        toast.success(`Job ${event.jobId} completed successfully.`, {
          duration: Number.POSITIVE_INFINITY,
          closeButton: true,
        });
      } else if (event.status === "failed") {
        toast.error(`Job ${event.jobId} failed.`);
      }
      upsert({
        jobId: event.jobId,
        status: event.status,
        progress: event.progress,
        completed_at: event.completed_at,
        started_at: event.started_at,
      });
    });
  }, [upsert]);

  return null;
}
