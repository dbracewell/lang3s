import { Lang3sSearchParamsLoader } from "@/features/search/server/searchParamsLoader";
import { SearchViewPage } from "@/features/search/ui/views/SearchViewPage";
import { trpc, prefetch } from "@/lib/trpc/server";

const SearchPage = async (props: PageProps<"/search">) => {
  const searchParams = await Lang3sSearchParamsLoader(props.searchParams);
  prefetch(trpc.search.search.infiniteQueryOptions({ ...searchParams }));
  return <SearchViewPage searchParams={searchParams} />;
};

export default SearchPage;
