"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { Sentence } from "@/features/documents/ui/components/Sentence";
import { Lan3gsDocument } from "@/features/nlp/classes";
import { useEffect, useState } from "react";
import { OntologySelectorDialog } from "@/features/ontology/ui/components/OntologySelectorDialog";
import { PaletteIcon } from "lucide-react";
import { useTags } from "@/features/documents/hooks/useTags";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { z } from "zod";
import { DocumentSchema } from "@/features/nlp/schemas";
import { useQuery } from "@tanstack/react-query";
import { ontologyGetAnnotationsForDocumentOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { DEFAULT_ONTOLOGY_COLOR } from "@/features/common/constants";
import { Spinner } from "@/components/Spinner";

type DocumentViewProps = {
  documentData: z.infer<typeof DocumentSchema>;
};

export const DocumentView = ({ documentData }: DocumentViewProps) => {
  // const document = new Lan3gsDocument({ ...documentData });
  const [document, setDocument] = useState<Lan3gsDocument | null>(null);
  const [checkedNodes, setCheckedNodes] = useTags();
  const { setContext } = useChatContext();
  useEffect(
    () => setContext(documentData.text.content),
    [documentData, setContext],
  );
  const { data: ontologyMapping } = useQuery({
    ...ontologyGetAnnotationsForDocumentOptions({
      client: coreClient,
      path: {
        doc_id: documentData.id,
      },
    }),
  });

  useEffect(() => {
    if (ontologyMapping != null) {
      setDocument(
        new Lan3gsDocument({
          ...documentData,
          text: {
            ...documentData.text,
            annotations: documentData.text.annotations.map((annotation) => ({
              ...annotation,
              value:
                ontologyMapping.mapping[annotation.id]?.path ??
                annotation.value,
              color:
                ontologyMapping.mapping[annotation.id]?.color ??
                DEFAULT_ONTOLOGY_COLOR,
            })),
          },
        }),
      );
    }
  }, [ontologyMapping, setDocument, documentData]);

  if (document == null) {
    return <Spinner />;
  }

  return (
    <ScrollableBox.Container className="bg-background gap-3 py-2 inset-shadow-sm">
      <ScrollableBox.ScrollArea className="gap-2">
        {document.text?.sentences.map((s, i) => (
          <Sentence key={i} index={i} sentence={s} annotations={checkedNodes} />
        ))}
      </ScrollableBox.ScrollArea>
      <OntologySelectorDialog
        trigger={
          <>
            <PaletteIcon /> Select annotations to view
          </>
        }
        size="sm"
        variant="listButton"
        className="w-fit"
        defaultCheckedNodes={checkedNodes}
        onSelect={setCheckedNodes}
      />
    </ScrollableBox.Container>
  );
};
