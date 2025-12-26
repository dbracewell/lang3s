"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { Sentence } from "@/components/text/Sentence";
import { cn } from "@/lib/utils/cn";
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
      <ScrollableBox.Container className="bg-background py-2 inset-shadow-sm">
        <ScrollableBox.ScrollArea className="gap-2">
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
    );
  },
);
