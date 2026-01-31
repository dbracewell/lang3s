import { useEffect } from "react";
import { eventBus } from "@/lib/events/eventBus";
import { toast } from "sonner";
import { useSetAtom } from "jotai";
import { updateAnalyticsProgressAtom } from "@/features/events/stores/update-analytics-stores";

export function useAnalyticsUpdate() {
  const setStatus = useSetAtom(updateAnalyticsProgressAtom);
  useEffect(() => {
    return eventBus.on("analytics_update", (e) => {
      setStatus((prev) => [...prev, e]);
      if (e.completed) {
        toast.info(
          "Successfully updated the analytics to reflect recent ontology changes",
          {
            closeButton: true,
            duration: Number.POSITIVE_INFINITY,
          },
        );
      } else {
        toast.error(
          "Failed to update the analytics to reflect recent ontology changes",
          {
            closeButton: true,
            duration: Number.POSITIVE_INFINITY,
          },
        );
      }
    });
  }, [setStatus]);
}
