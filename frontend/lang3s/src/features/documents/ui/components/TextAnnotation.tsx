import { Button } from "@/components/ui/button";
import { formatURL } from "@/lib/utils/formatters";
import { cn } from "@/lib/utils/cn";
import { Lang3sTextAnnotation } from "@/features/nlp/classes";
import {
  AnnotationColors,
  DEFAULT_MIN_SIMILARITY,
  ONTOLOGY_ENTITY_ROOT,
} from "@/features/common/constants";
import { SearchIcon } from "lucide-react";
import Link from "next/link";
import React, { memo } from "react";

const isEventive = (type: string) => {
  return !isEntity(type);
};

const isEntity = (type: string) => type.startsWith(ONTOLOGY_ENTITY_ROOT);

const getGroupName = (
  annotation: Lang3sTextAnnotation | null,
  isEvent: boolean = false,
) => {
  let groupName = "";
  if (annotation == null) {
    return groupName;
  }
  if (isEntity(annotation.value)) {
    groupName = isEvent ? annotation.id : annotation.COREF().id;
  } else if (isEventive(annotation.value)) {
    groupName = annotation.id;
  } else {
    groupName = annotation.value;
  }
  return groupName.toUpperCase().replaceAll(" ", "_");
};

const opacity = "opacity-60";

const blurSentence = () => {
  const divsWithAttribute = document.querySelectorAll(
    `div[data-annotation="${true}"]`,
  );
  divsWithAttribute.forEach((ele) => {
    const div = ele as HTMLDivElement;
    div.classList.add(opacity);
  });
};
const highlightGroup = (
  attribute: string,
  groupName: string,
  data?: string,
) => {
  const divsWithAttribute = document.querySelectorAll(
    `div[data-${attribute}="${groupName}"]`,
  );
  divsWithAttribute.forEach((ele) => {
    const div = ele as HTMLDivElement;
    div.classList.add(
      "outline",
      "outline-dashed",
      "shadow",
      "border-dashed",
      "relative",
      "z-1",
      "scale-102",
    );
    div.classList.remove(opacity);
    if (data != null) {
      div.dataset.annotationType = data;
    }
  });
};

const unhighlightGroup = (attribute: string, groupName: string) => {
  const divsWithAttribute = document.querySelectorAll(
    `div[data-${attribute}="${groupName}"]`,
  );
  divsWithAttribute.forEach((ele) => {
    const div = ele as HTMLDivElement;
    div.classList.remove(
      "outline",
      "outline-dashed",
      "shadow",
      "border-dashed",
      "relative",
      "z-1",
      "scale-102",
    );
    div.dataset.annotationType = div.dataset.type;
  });
};

const unblurSentence = () => {
  const divsWithAttribute = document.querySelectorAll(
    `div[data-annotation="${true}"]`,
  );
  divsWithAttribute.forEach((ele) => {
    const div = ele as HTMLDivElement;
    div.classList.remove(opacity);
  });
};

export const TextAnnotation = memo(
  ({ annotation }: { annotation: Lang3sTextAnnotation }) => {
    return (
      <div className={cn("relative", annotation.type != "token" && "group")}>
        <div
          data-annotation-type={
            annotation.type != "token"
              ? annotation.value.split(".").slice(-1)[0]
              : ""
          }
          data-type={annotation.value.split(".").slice(-1)[0]}
          data-annotation={true}
          data-entity={getGroupName(annotation)}
          data-event={getGroupName(annotation, true)}
          onMouseEnter={() => {
            if (annotation.type === "token") return;
            blurSentence();
            highlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation, isEventive(annotation.value)),
            );
            annotation.A0().map((a) => {
              highlightGroup(
                isEventive(annotation.value) ? "event" : "entity",
                getGroupName(a, true),
                "A0",
              );
            });
            annotation.A1().map((a) => {
              highlightGroup(
                isEventive(annotation.value) ? "event" : "entity",
                getGroupName(a, true),
                "A1",
              );
            });
            highlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation.TIME(), true),
              "TIME",
            );
            highlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation.LOC(), true),
              "LOC",
            );
          }}
          onMouseLeave={() => {
            if (annotation.type === "token") return;
            unblurSentence();
            unhighlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation, isEventive(annotation.value)),
            );
            annotation.A0().map((a) => {
              unhighlightGroup(
                isEventive(annotation.value) ? "event" : "entity",
                getGroupName(a, true),
              );
            });
            annotation.A1().map((a) => {
              unhighlightGroup(
                isEventive(annotation.value) ? "event" : "entity",
                getGroupName(a, true),
              );
            });
            unhighlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation.TIME(), true),
            );
            unhighlightGroup(
              isEventive(annotation.value) ? "event" : "entity",
              getGroupName(annotation.LOC(), true),
            );
          }}
          className={cn(
            "text-black",
            annotation.type === "token"
              ? "text-foreground pt-0.5"
              : "entity cursor-pointer rounded-md border border-amber-500 bg-amber-100 after:bg-amber-500 after:p-px after:text-center after:text-[10px] after:text-white after:uppercase",
            annotation.type !== "token" && AnnotationColors[annotation.color],
          )}
        >
          <div className={cn(annotation.type !== "token" && "px-2")}>
            {annotation.text}{" "}
          </div>
        </div>
        <div className="absolute -top-2 -right-2 z-5 hidden group-hover:flex">
          <Button
            size="icon-sm"
            className={cn(
              "flex size-5 items-center justify-center border p-0!",
            )}
            asChild
          >
            <Link
              href={formatURL("/search", {
                aid: annotation.id,
                minSimilarity: DEFAULT_MIN_SIMILARITY,
                stype: "annotation",
                semantic: true,
                atype: annotation.type,
                q: `"${annotation.text}"`,
                isStrict: false,
              })}
            >
              <SearchIcon className="size-3" />
            </Link>
          </Button>
        </div>
      </div>
    );
  },
);
