import { DocumentIdView } from "@/modules/documents/ui/views/DocumentIdView";
import { caller } from "@/trpc/server";
import React from "react";

const DocumentIdPage = async (props: PageProps<"/documents/[id]">) => {
   const { id } = await props.params;
   const documentData = await caller.documents.getOne({ id });
   return <DocumentIdView documentData={documentData} />;
};

export default DocumentIdPage;
