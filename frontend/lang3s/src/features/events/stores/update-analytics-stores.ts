import { createLocalStorageStatusAtom } from "@/features/events/stores/create-status-atom";
import { atom } from "jotai";

export const updateAnalyticsProgressAtom =
  createLocalStorageStatusAtom<"analytics_update">();

export const popUpdateAnalyticsProgressAtom = atom(null, (_, set) => {
  set(updateAnalyticsProgressAtom, (prev) => []);
});
