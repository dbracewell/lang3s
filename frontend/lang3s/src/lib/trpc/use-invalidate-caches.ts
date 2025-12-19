import { useTRPC } from "@/lib/trpc/client";
import { AppRouter } from "@/lib/trpc/routers/_app";
import { QueryFilters, useQueryClient } from "@tanstack/react-query";
import { TRPCOptionsProxy } from "@trpc/tanstack-react-query";

type InvalidateFn = (trpc: TRPCOptionsProxy<AppRouter>) => QueryFilters[];

export const useInvalidateCaches = () => {
  const queryClient = useQueryClient();
  const trpc = useTRPC();

  return async (fn: InvalidateFn) => {
    const filters = fn(trpc);
    return await Promise.all(
      filters.map((filter) => queryClient.invalidateQueries(filter)),
    );
  };
};
