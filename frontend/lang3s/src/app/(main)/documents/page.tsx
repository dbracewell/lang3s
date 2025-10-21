import { DocumentsViewPage } from "@/modules/documents/ui/views/DocumentsViewPage";
import { HydrateClient, prefetch, trpc } from "@/trpc/server";
import React from "react";

const DocumentsPage = () => {
   prefetch(trpc.documents.getMany.infiniteQueryOptions({ cursor: 0 }));
   return (
      <HydrateClient>
         <DocumentsViewPage />
      </HydrateClient>
   );
};

export default DocumentsPage;
