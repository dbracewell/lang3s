"use client";
import { ScrollableBox } from "@/components/Scrollbox";
import { Sentence } from "@/components/text/Sentence";
import { cn } from "@/lib/utils";
import { Lan3gsDocument } from "@/modules/common/classes";
import { AnnotationColors } from "@/modules/common/constants";
import { GetDocumentResult } from "@/modules/documents/types";

type DocumentViewProps = {
  documentData: GetDocumentResult;
  targetAnnotationType: string;
  viewAnnotationList?: boolean;
};

export const DocumentView = ({
  documentData,
  targetAnnotationType,
  viewAnnotationList = true,
}: DocumentViewProps) => {
  const document = new Lan3gsDocument({ ...documentData });
  const allAnnotations =
    document.text?.annotationsByType(targetAnnotationType) ?? [];
  const allValues = new Set(allAnnotations.map((a) => a.value));

  const spanColors: Record<string, string> = {
    LOC: "GREEN",
    MISC: "RED",
    ORG: "BLUE",
    DATE: "YELLOW",
    CARDINAL: "GRAY",
    PERSON: "PURPLE",
    NP: "GREEN",
    VP: "RED",
    ADJP: "BLUE",
    ADVP: "YELLOW",
  };
  const DEFAULT = "SLATE";

  return (
    <div
      className={cn(
        "grid min-h-0 flex-1 grid-cols-1 gap-2",
        viewAnnotationList
          ? "grid-cols-1 grid-rows-[4fr_2fr] md:grid-cols-[4fr_1fr] md:grid-rows-1"
          : "grid-cols-1",
      )}
    >
      <ScrollableBox.Container className="bg-white py-2 inset-shadow-sm">
        <ScrollableBox.ScrollArea className="gap-2 px-5 pr-2">
          {document.text?.sentences.map((s, i) => (
            <Sentence
              key={i}
              lang={document.metadata["language"]}
              index={i}
              sentence={s}
              colors={spanColors}
              defaultColor={DEFAULT}
              targetAnnotation={targetAnnotationType}
            />
          ))}
        </ScrollableBox.ScrollArea>
      </ScrollableBox.Container>
      {viewAnnotationList && (
        <ScrollableBox.Container className="bg-white">
          <ScrollableBox.Header>{targetAnnotationType}</ScrollableBox.Header>
          <ScrollableBox.ScrollArea className="gap-2 px-3">
            {[...allValues].map((v, idx) => (
              <div key={idx}>
                <div
                  className={cn(
                    "rounded-t-md border p-1 pl-4",
                    AnnotationColors[spanColors[v] ?? DEFAULT],
                  )}
                >
                  {v}
                </div>
                <ul
                  className={cn(
                    "cols list-inside list-disc gap-0.5 rounded-b-md border border-t-0 bg-white p-2",
                    AnnotationColors[spanColors[v] ?? DEFAULT].replace(
                      /bg-[a-z]+-\d+/,
                      "",
                    ),
                  )}
                >
                  {[
                    ...new Set(
                      allAnnotations
                        .filter((a) => a.value === v)
                        .map((a) => a.text),
                    ),
                  ].map((a, idx) => (
                    <li key={idx} className="pl-2 text-xs">
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </ScrollableBox.ScrollArea>
        </ScrollableBox.Container>
      )}
    </div>
  );
};
