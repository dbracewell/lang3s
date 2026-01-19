import { RouterOutputs } from "@/lib/trpc/types";
import Link from "next/link";

export const DocumentResult = ({
  doc,
}: {
  doc: RouterOutputs["documents"]["getMany"]["posts"][number];
}) => {
  return (
    <div className="flex w-full flex-col px-2 py-3">
      <Link href={`/documents/${doc.id}`} className="link mb-1 text-lg">
        {doc.title}
      </Link>
      <p className="mb-0.5 text-base">{doc.text}</p>
    </div>
  );
};
