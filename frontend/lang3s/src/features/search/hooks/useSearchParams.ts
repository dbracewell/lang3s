import { useQueryStates } from "nuqs";
import { SearchQueryParams } from "@/features/search/schemas";

export const useGlobalSearchParams = () => {
  return useQueryStates(SearchQueryParams);
};
