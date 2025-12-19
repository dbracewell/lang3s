import { TextAnnotation } from "@/components/text/TextAnnotation";
import { cn } from "@/lib/utils/cn";
import { Lang3sTextAnnotation } from "@/features/common/classes";
import { memo } from "react";
import { useOntologyColors } from "@/features/ontology/hooks";

type SentenceProps = {
  sentence: Lang3sTextAnnotation;
  targetAnnotation: string;
  index: number;
};

export const Sentence = memo(
  ({ sentence, targetAnnotation, index }: SentenceProps) => {
    const { getOntologyColor } = useOntologyColors();

    return (
      <div className="flex items-center justify-between gap-2">
        <div
          data-sentence={"true"}
          className={cn(
            "flex flex-1 flex-wrap items-start gap-1 rounded-md border p-2 text-sm",
            index % 2 == 0
              ? "bg-white dark:bg-zinc-900"
              : "bg-gray-100 dark:bg-zinc-800",
          )}
        >
          {sentence
            .interleave([
              targetAnnotation,
              "event",
              "relation",
              "process",
              "state",
            ])
            .map((t, z) => (
              <TextAnnotation
                key={z}
                annotation={t}
                color={getOntologyColor(t.value)}
              />
            ))}
        </div>
        <div className="flex w-[20px] flex-col gap-0.5"></div>
      </div>
    );
  },
);
