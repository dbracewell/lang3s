import { useEffect, useState } from "react";
import { eventBus } from "@/lib/events/eventBus";

export function useJobProgress(jobId: string) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    return eventBus.on("job:update", (e) => {
      if (e.jobId === jobId) {
        setProgress(e.progress);
      }
    });
  }, [jobId]);

  return progress;
}
