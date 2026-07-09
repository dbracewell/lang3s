"use client";

import { useEffect } from "react";
import { eventBus } from "@/lib/events/eventBus";
import { useQueryClient } from "@tanstack/react-query";
import { jobsGetRunningCountQueryKey } from "@/clients/core/@tanstack/react-query.gen";
import { toast } from "sonner";

export function OntologyUpdateListener() {
  const queryClient = useQueryClient();

  useEffect(() => {
    return eventBus.on("analytics:update", (event) => {
      if (event.completed) {
        toast.success("Ontology updates finished publishing");
      }
      queryClient.invalidateQueries({
        queryKey: jobsGetRunningCountQueryKey({
          path: {
            job_type: "analyticsupdate",
          },
        }),
      });
    });
  }, [queryClient]);

  return null;
}
