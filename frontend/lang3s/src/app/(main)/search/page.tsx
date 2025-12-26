import { Lang3sSearchParamsLoader } from "@/features/search/server/searchParamsLoader";
import { SearchViewPage } from "@/features/search/ui/views/SearchViewPage";

const SearchPage = async (props: PageProps<"/search">) => {
  const searchParams = await Lang3sSearchParamsLoader(props.searchParams);
  return <SearchViewPage searchParams={searchParams} />;
};

export default SearchPage;
