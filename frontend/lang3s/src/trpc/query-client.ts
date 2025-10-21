import {
  defaultShouldDehydrateQuery,
  MutationCache,
  QueryClient,
} from "@tanstack/react-query";
import superjson from "superjson";

export function makeQueryClient() {
  const queryClient = new QueryClient({
    mutationCache: new MutationCache({
      onSuccess: () => {
        queryClient.invalidateQueries();
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 5 * 30 * 1000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },

      dehydrate: {
        serializeData: superjson.serialize,
        shouldDehydrateQuery: (query) =>
          defaultShouldDehydrateQuery(query) ||
          query.state.status === "pending",
      },
      hydrate: {
        deserializeData: superjson.deserialize,
      },
    },
  });
  return queryClient;
}
