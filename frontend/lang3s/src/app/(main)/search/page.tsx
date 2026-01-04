import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { SearchTabButtons } from "@/features/search/ui/components/SearchTabButtons";
import { DocumentSearchView } from "@/features/search/ui/views/DocumentSearchView";
import { AnnotationSearchView } from "@/features/search/ui/views/AnnotationSearchView";
import React from "react";
import { TopicSearchView } from "@/features/search/ui/views/TopicsSearchView";
import { SearchResultParameters } from "@/features/search/ui/components/SearchResultParameters";
import { getUser, roleHasPermissions } from "@/features/auth/server/actions";
import { FolderPlusIcon } from "lucide-react";
import { CreateProjectDialog } from "@/features/projects/ui/components/CreateProjectDialog";

const SearchPage = async () => {
  const user = await getUser();
  const hasProjectPermission = await roleHasPermissions(user.role, [
    "project:create",
    "project:update",
  ]);
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
        <DocumentSearchView />
        <AnnotationSearchView />
        <TopicSearchView />
      </div>
    </ScrollableBox.Container>
  );
};

export default SearchPage;
