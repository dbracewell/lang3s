import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { SearchTabButtons } from "@/features/search/ui/components/SearchTabButtons";
import React from "react";
import { SearchResultParameters } from "@/features/search/ui/components/SearchResultParameters";
import { getUser, roleHasPermissions } from "@/features/auth/server/actions";
import { CreateProjectDialog } from "@/features/projects/ui/components/CreateProjectDialog";
import { SearchTabList } from "@/features/search/ui/views/SearchTabList";
import { getQueryClient, prefetch, trpc } from "@/lib/trpc/server";
import { createLoader } from "nuqs/server";
import { SearchQueryParams } from "@/features/search/schemas";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

const SearchPage = async (props: PageProps<"/search">) => {
  const user = await getUser();
  const paramsLoader = createLoader(SearchQueryParams);
  const { tab, ...rest } = await paramsLoader(props.searchParams);
  void prefetch(
    trpc.search.searchAnnotations.infiniteQueryOptions(
      { ...rest },
      {
        getNextPageParam: (lastPage) => lastPage?.nextCursor,
      },
    ),
  );
  const hasProjectPermission = await roleHasPermissions(user.role, [
    "project:create",
    "project:update",
  ]);
  const queryClient = getQueryClient();
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <div className="flex flex-1 items-center justify-between">
          <h1>Search Results</h1>
          {hasProjectPermission && (
            <>
              <CreateProjectDialog />
            </>
          )}
        </div>
        <SearchResultParameters />
      </ScrollableBox.Header>
      <div className="flex h-full min-h-0 flex-col gap-1 overflow-hidden">
        <SearchTabButtons />
        <HydrationBoundary state={dehydrate(queryClient)}>
          <SearchTabList />
        </HydrationBoundary>
      </div>
    </ScrollableBox.Container>
  );
};

export default SearchPage;
