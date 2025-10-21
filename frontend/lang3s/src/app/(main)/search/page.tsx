import { QueryType, QueryTypes } from "@/modules/search/types";
import { SearchViewPage } from "@/modules/search/ui/views/SearchViewPage";
import { parseSearchParams } from "@/modules/search/utils/parse-params";
import { caller } from "@/trpc/server";
import React from "react";

const SearchPage = async (props: PageProps<"/search">) => {
   const searchParams = await props.searchParams;

   const results = await caller.search.search({
      ...parseSearchParams(searchParams),
   });

   return <SearchViewPage results={results} />;
};

export default SearchPage;
