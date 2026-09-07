"use client";
import { ontologyGetAnnotationsForDocumentOptions } from "@/clients/core/@tanstack/react-query.gen";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { Spinner } from "@/components/Spinner";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { useTags } from "@/features/documents/hooks/useTags";
import { Sentence } from "@/features/documents/ui/components/Sentence";
import { OntologySelectorDialog } from "@/features/ontology/ui/components/OntologySelectorDialog";
import { coreClient } from "@/lib/api";
import { DEFAULT_ONTOLOGY_COLOR } from "@/lib/constants";
import { Lan3gsDocument } from "@/lib/nlp/classes";
import { DocumentSchema } from "@/lib/nlp/schemas";
import { useQuery } from "@tanstack/react-query";
import { PaletteIcon } from "lucide-react";
import { useEffect, useMemo } from "react";
import { z } from "zod";

type DocumentViewProps = {
  documentData: z.infer<typeof DocumentSchema>;
};

export const DocumentView = ({ documentData }: DocumentViewProps) => {
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

  const document = useMemo(() => {
    if (ontologyMapping == null) {
      return null;
    }

    return new Lan3gsDocument({
      ...documentData,
      text: {
        ...documentData.text,
        annotations: documentData.text.annotations?.map((annotation) => ({
          ...annotation,
          value:
            ontologyMapping.mapping[annotation.id as string]?.path ??
            annotation.value,
          color:
            ontologyMapping.mapping[annotation.id as string]?.color ??
            DEFAULT_ONTOLOGY_COLOR,
        })),
      },
    });
  }, [ontologyMapping, documentData]);

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
