import React from "react";
import { HydrateClient, prefetch, trpc } from "@/lib/trpc/server";
import {
  DocumentsViewPage,
  DocumentsViewPageSkeleton,
} from "@/features/documents/ui/views/DocumentsViewPage";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

const DocumentsPage = () => {
  prefetch(trpc.documents.getMany.infiniteQueryOptions({ cursor: 0 }));
  return (
    <ScrollableBox.Container className="gap-2">
      <ScrollableBox.Header>
        <h1>Documents</h1>
      </ScrollableBox.Header>
      <HydrateClient fallback={<DocumentsViewPageSkeleton />}>
        <DocumentsViewPage />
      </HydrateClient>
    </ScrollableBox.Container>
  );
};

export default DocumentsPage;
