import { TextAnnotation } from "@/components/text/TextAnnotation";
import { cn } from "@/lib/utils";
import { Lang3sTextAnnotation } from "@/modules/common/classes";
import { NotepadTextIcon } from "lucide-react";
import { memo } from "react";

type SentenceProps = {
  sentence: Lang3sTextAnnotation;
  targetAnnotation: string;
  colors: Record<string, string>;
  defaultColor: string;
  index: number;
  lang: string;
};

export const Sentence = memo(
  ({
    sentence,
    targetAnnotation,
    colors,
    defaultColor,
    index,
    lang,
  }: SentenceProps) => {
    return (
      <div className="flex items-center justify-between gap-2">
        <div
          data-sentence={"true"}
          className={cn(
            "flex flex-1 flex-wrap items-start gap-1 rounded-md border p-2 text-sm",
            index % 2 == 0 ? "bg-white" : "bg-gray-100",
          )}
        >
          {sentence.interleave([targetAnnotation, "event"]).map((t, z) => (
            <TextAnnotation
              key={z}
              lang={lang}
              annotation={t}
              targetType={targetAnnotation}
              color={colors[t.value] ?? defaultColor}
            />
          ))}
        </div>
        <div className="flex w-[20px] flex-col gap-0.5"></div>
      </div>
    );
  },
);
