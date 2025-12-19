import React from "react";
import { HydrateClient, prefetch, trpc } from "@/lib/trpc/server";
import { DocumentsViewPage } from "@/features/documents/ui/views/DocumentsViewPage";
import { Spinner } from "@/components/Spinner";

const DocumentsPage = () => {
  prefetch(trpc.documents.getMany.infiniteQueryOptions({ cursor: 0 }));
  return (
    <HydrateClient fallback={<Spinner />}>
      <DocumentsViewPage />
    </HydrateClient>
  );
};

export default DocumentsPage;
