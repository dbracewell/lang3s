import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { SearchTabButtons } from "@/features/search/ui/components/SearchTabButtons";
import React from "react";
import { SearchResultParameters } from "@/features/search/ui/components/SearchResultParameters";
import { SearchTabList } from "@/features/search/ui/views/SearchTabList";

const SearchPage = async () => {
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <div className="flex flex-1 items-center justify-between">
          <h1>Search Results</h1>
        </div>
        <SearchResultParameters />
      </ScrollableBox.Header>
      <div className="flex h-full min-h-0 flex-col gap-1 overflow-hidden">
        <SearchTabButtons />
        <SearchTabList />
      </div>
    </ScrollableBox.Container>
  );
};

export default SearchPage;
