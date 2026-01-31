import { useEffect } from "react";
import { useAtomValue, useSetAtom } from "jotai";
import {
  popUpdateAnalyticsProgressAtom,
  updateAnalyticsProgressAtom,
} from "@/features/events/stores/update-analytics-stores";

export const useAnalyticsUpdateMonitor = (onComplete: () => Promise<void>) => {
  const state = useAtomValue(updateAnalyticsProgressAtom);
  const pop = useSetAtom(popUpdateAnalyticsProgressAtom);
  useEffect(() => {
    const complete = async () => {
      pop();
      await onComplete();
    };

    if (state.length > 0) {
      complete();
    }
  }, [state, onComplete, pop]);
};
