import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { SearchTabButtons } from "@/features/search/ui/components/SearchTabButtons";
import { DocumentSearchView } from "@/features/search/ui/views/DocumentSearchView";
import { AnnotationSearchView } from "@/features/search/ui/views/AnnotationSearchView";
import React from "react";
import { TopicSearchView } from "@/features/search/ui/views/TopicsSearchView";
import { SearchResultParameters } from "@/features/search/ui/components/SearchResultParameters";

const SearchPage = async (props: PageProps<"/search">) => {
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Search Results</h1>
        <SearchResultParameters />
      </ScrollableBox.Header>
      <div className="flex h-full min-h-0 flex-col gap-1 overflow-hidden">
        <SearchTabButtons />
        <DocumentSearchView />
        <AnnotationSearchView />
        <TopicSearchView />
      </div>
    </ScrollableBox.Container>
  );
};

export default SearchPage;
