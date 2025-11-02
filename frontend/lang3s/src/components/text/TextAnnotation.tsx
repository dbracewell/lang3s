import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Lang3sTextAnnotation } from "@/modules/common/classes";
import { AnnotationColors } from "@/modules/common/constants";
import { SearchIcon } from "lucide-react";
import Link from "next/link";
import React from "react";

export const TextAnnotation = ({
  annotation,
  targetType,
  lang,
  color,
}: {
  annotation: Lang3sTextAnnotation;
  targetType?: string;
  lang: string;
  color: string;
}) => {
  return (
    <div className={cn("relative", annotation.type === targetType && "group")}>
      <div
        data-annotation-type={
          annotation.type === targetType ? annotation.value : ""
        }
        className={cn(
          "cols entity",
          annotation.type === targetType
            ? "overflow-clip rounded-md border border-amber-500 bg-amber-100 px-2 text-center after:-mx-2 after:bg-amber-500 after:p-[1px] after:text-center after:text-[10px] after:text-white after:uppercase"
            : "pt-0.5",
          annotation.type === targetType && AnnotationColors[color],
        )}
      >
        {annotation.text}
      </div>
      <div className="absolute -top-2 -right-2 hidden group-hover:flex">
        <Button size="icon-sm" className="size-5 p-0!" asChild>
          <Link
            href={`/search/?aid=${
              annotation.id
            }&atype=${targetType}&minSimilarity=0.7&type=annotation&semantic=true&q=${encodeURIComponent(
              annotation.text,
            )}&lang=${lang}`}
          >
            <SearchIcon className="size-3" />
          </Link>
        </Button>
      </div>
    </div>
  );
};
