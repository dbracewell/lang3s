// import React from "react";
// import { prefetch, trpc } from "@/trpc/server";
// import { DocumentsViewPage } from "@/features/documents/ui/views/DocumentsViewPage";
//
// const DocumentsPage = () => {
//   prefetch(trpc.documents.getMany.infiniteQueryOptions({ cursor: 0 }));
//   return (
//     // <HydrateClient fallback={<Spinner />}>
//     <DocumentsViewPage />
//     // </HydrateClient>
//   );
// };
//
// export default DocumentsPage;

// import React from "react";
// import { prefetch, trpc } from "@/trpc/server";
// import { DocumentsViewPage } from "@/features/documents/ui/views/DocumentsViewPage";
//
// const DocumentsPage = () => {
//   prefetch(trpc.documents.getMany.infiniteQueryOptions({ cursor: 0 }));
//   return (
//     // <HydrateClient fallback={<Spinner />}>
//     <DocumentsViewPage />
//     // </HydrateClient>
//   );
// };
//
// export default DocumentsPage;
import { db } from "@/lib/db";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { jsonAgg, jsonBuildObject, orderAsc } from "@/lib/db/funcs";
import { eq } from "drizzle-orm";

type AnnotationType = {
  id: string;
  text: string;
  type: string;
};

export default async function DocumentsPage() {
  const results = await db
    .select({
      doc_id: TextAnnotationTable.documentId,
      json: jsonAgg(
        jsonBuildObject({
          id: TextAnnotationTable.id,
          text: TextAnnotationTable.text,
          type: TextAnnotationTable.type,
        }),
        orderAsc(TextAnnotationTable.start),
      ).as("json"),
    })
    .from(TextAnnotationTable)
    .where(eq(TextAnnotationTable.type, "sentence"))
    .groupBy((t) => [t.doc_id])
    .limit(10);

  return (
    <div className="scrollable flex-1 space-y-10">
      {results.map((row) => (
        <div key={row.doc_id} className="flex flex-col gap-1">
          {row.json.map((sentence) => (
            <div key={sentence.id}>{sentence.text}</div>
          ))}
        </div>
      ))}
    </div>
  );
}
