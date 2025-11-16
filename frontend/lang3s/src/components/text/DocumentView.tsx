"use client";
import { ScrollableBox } from "@/components/Scrollbox";
import { Sentence } from "@/components/text/Sentence";
import { cn } from "@/lib/utils";
import { Lan3gsDocument } from "@/features/common/classes";
import { GetDocumentResult } from "@/features/documents/types";
import { memo } from "react";

type DocumentViewProps = {
  documentData: GetDocumentResult;
  targetAnnotationType: string;
};

export const DocumentView = memo(
  ({ documentData, targetAnnotationType }: DocumentViewProps) => {
    const document = new Lan3gsDocument({ ...documentData });
    return (
      <div className={cn("grid min-h-0 flex-1 grid-cols-1 gap-2")}>
        <ScrollableBox.Container className="bg-white py-2 inset-shadow-sm">
          <ScrollableBox.ScrollArea className="gap-2 px-5 pr-2">
            {document.text?.sentences.map((s, i) => (
              <Sentence
                key={i}
                index={i}
                sentence={s}
                targetAnnotation={targetAnnotationType}
              />
            ))}
          </ScrollableBox.ScrollArea>
        </ScrollableBox.Container>
      </div>
    );
  },
);
