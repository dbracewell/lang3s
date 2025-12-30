import { useEffect } from "react";
import { eventBus } from "@/lib/events/eventBus";
import { toast } from "sonner";

export function useAnalyticsUpdate() {
  useEffect(() => {
    return eventBus.on("analytics_update", (e) => {
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
  }, []);
}
