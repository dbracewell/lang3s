import Link from "next/link";
import { DocumentInfo } from "@/client";

export const DocumentResult = ({ doc }: { doc: DocumentInfo }) => {
  return (
    <div className="flex w-full flex-col px-2 py-3">
      <Link href={`/documents/${doc.id}`} className="link mb-1 text-lg">
        {doc.title}
      </Link>
      <p className="mb-0.5 text-base">{doc.snippet}</p>
    </div>
  );
};
