"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { Sentence } from "@/components/text/Sentence";
import { Lan3gsDocument } from "@/features/common/classes";
import { memo, useState } from "react";
import { OntologySelectorDialog } from "@/features/ontology/ui/components/OntologySelectorDialog";
import { PaletteIcon } from "lucide-react";
import { RouterOutputs } from "@/lib/trpc/types";

type DocumentViewProps = {
  documentData: RouterOutputs["documents"]["getOne"];
};

export const DocumentView = memo(({ documentData }: DocumentViewProps) => {
  const document = new Lan3gsDocument({ ...documentData });
  const [checkedNodes, setCheckedNodes] = useState<string[]>(["ALL.Entity"]);
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
});
