import { Lang3sSearchParamsLoader } from "@/features/search/server/searchParamsLoader";
import { SearchViewPage } from "@/features/search/ui/views/SearchViewPage";
import { caller } from "@/trpc/server";

const SearchPage = async (props: PageProps<"/search">) => {
  const searchParams = await Lang3sSearchParamsLoader(props.searchParams);
  const results = await caller.search.search(searchParams);
  return <SearchViewPage results={results} />;
};

export default SearchPage;
