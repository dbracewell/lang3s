"use client";

import { useEffect } from "react";
import { useSetAtom } from "jotai";
import { eventBus } from "@/lib/events/eventBus";
import { upsertJobStatusAtom } from "@/features/jobs/stores/jobStatus";
import { toast } from "sonner";

export function JobStatusListener() {
  const upsert = useSetAtom(upsertJobStatusAtom);

  useEffect(() => {
    return eventBus.on("job:update", (event) => {
      if (event.status === "complete") {
        toast.success(`Job ${event.jobId} completed successfully.`);
      } else if (event.status === "failed") {
        toast.error(`Job ${event.jobId} failed.`);
      }
      upsert({
        jobId: event.jobId,
        status: event.status,
        progress: event.progress,
      });
    });
  }, [upsert]);

  return null;
}
