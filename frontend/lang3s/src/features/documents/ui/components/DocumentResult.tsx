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
      <div className="bg-gray-200 p-2 pt-2 dark:bg-gray-900">
        <h2 className="text-sm font-semibold">Entities</h2>
        <div className="flex items-center gap-1 overflow-x-auto">
          {doc.entities.slice(0, 5).map((e, i) => (
            <div
              key={i}
              className="text-xs"
              dangerouslySetInnerHTML={{
                __html: (i > 0 ? " | " : "") + e,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
