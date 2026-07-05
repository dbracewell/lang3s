import { TextAnnotation } from "@/features/documents/ui/components/TextAnnotation";
import { cn } from "@/lib/utils/cn";
import { Lang3sTextAnnotation } from "@/lib/nlp/classes";

type SentenceProps = {
  sentence: Lang3sTextAnnotation;
  annotations: string[];
  index: number;
};

export const Sentence = ({ sentence, annotations, index }: SentenceProps) => {
  return (
    <div className="flex items-center justify-between gap-2">
      <div
        data-sentence={"true"}
        className={cn(
          "flex flex-1 flex-wrap items-start gap-1 p-2 text-sm",
          index % 2 == 0
            ? "bg-white dark:bg-zinc-900"
            : "bg-gray-100 dark:bg-zinc-800",
        )}
      >
        {sentence.interleave(annotations).map((t, z) => (
          <TextAnnotation key={z} annotation={t} />
        ))}
      </div>
    </div>
  );
};
