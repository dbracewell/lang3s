"use client";

import { useEffect } from "react";
import { eventBus } from "@/lib/events/eventBus";
import { useQueryClient } from "@tanstack/react-query";
import { jobsListJobsQueryKey } from "@/clients/core/@tanstack/react-query.gen";
import { Job } from "@/clients/core";

export function JobStatusListener() {
  const queryClient = useQueryClient();

  useEffect(() => {
    return eventBus.on("job:update", (event) => {
      queryClient.setQueryData(jobsListJobsQueryKey(), (prev: Job[]) => {
        const isDeleting = event.deleting;
        if (!prev) {
          return isDeleting ? [] : [event];
        }
        const currentJob = prev.find((job) => job.id === event.id);
        if (currentJob) {
          return isDeleting
            ? prev.filter((job) => job.id !== event.id)
            : prev.map((job) => (job.id === event.id ? event : job));
        }
        return isDeleting ? prev : [...prev, event];
      });
    });
  }, [queryClient]);

  return null;
}
