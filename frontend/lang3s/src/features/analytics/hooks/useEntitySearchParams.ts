import { useQueryStates } from "nuqs";
import { entitySearchParams } from "@/features/analytics/lib/searchParams";

export const useEntitySearchParams = () => {
  return useQueryStates(entitySearchParams, {});
};
