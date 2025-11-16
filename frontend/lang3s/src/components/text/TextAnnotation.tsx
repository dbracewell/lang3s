import { Button } from "@/components/ui/button";
import { formatURL } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { Lang3sTextAnnotation } from "@/features/common/classes";
import { AnnotationColors } from "@/features/common/constants";
import { SearchIcon } from "lucide-react";
import Link from "next/link";
import React, { memo } from "react";

const isEventive = (type: string) => {
  return (
    type === "event" ||
    type == "process" ||
    type == "relation" ||
    type == "state"
  );
};

const getGroupName = (
  annotation: Lang3sTextAnnotation | null,
  isEvent: boolean = false,
) => {
  let groupName = "";
  if (annotation == null) {
    return groupName;
  }
  if (annotation.type === "entity") {
    groupName = isEvent ? annotation.id : annotation.COREF().id;
  } else if (isEventive(annotation.type)) {
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
    );
    div.classList.remove(opacity);
    if (data != null) {
      div.dataset.annotationType = data;
    }
  });
};

const unhighlightGroup = (
  attribute: string,
  groupName: string,
  data?: string,
) => {
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
    );
    if (data != null) {
      div.dataset.annotationType = data;
    }
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
  ({
    annotation,
    color,
  }: {
    annotation: Lang3sTextAnnotation;
    color: string;
  }) => {
    return (
      <div className={cn("relative", annotation.type != "token" && "group")}>
        <div
          data-annotation-type={
            annotation.type != "token" ? annotation.value : ""
          }
          data-annotation={true}
          data-entity={getGroupName(annotation)}
          data-event={getGroupName(annotation, true)}
          onMouseEnter={() => {
            if (annotation.type === "token") return;
            blurSentence();
            highlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation, isEventive(annotation.type)),
            );
            annotation.A0().map((a) => {
              highlightGroup(
                isEventive(annotation.type) ? "event" : "entity",
                getGroupName(a, true),
                "A0",
              );
            });
            annotation.A1().map((a) => {
              highlightGroup(
                isEventive(annotation.type) ? "event" : "entity",
                getGroupName(a, true),
                "A1",
              );
            });
            highlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation.TIME(), true),
              "TIME",
            );
            highlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation.LOC(), true),
              "LOC",
            );
          }}
          onMouseLeave={() => {
            if (annotation.type === "token") return;
            unblurSentence();
            unhighlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation, isEventive(annotation.type)),
            );
            annotation.A0().map((a) => {
              unhighlightGroup(
                isEventive(annotation.type) ? "event" : "entity",
                getGroupName(a, true),
                annotation.type,
              );
            });
            annotation.A1().map((a) => {
              unhighlightGroup(
                isEventive(annotation.type) ? "event" : "entity",
                getGroupName(a, true),
                annotation.type,
              );
            });
            unhighlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation.TIME(), true),
              annotation.type,
            );
            unhighlightGroup(
              isEventive(annotation.type) ? "event" : "entity",
              getGroupName(annotation.LOC(), true),
              annotation.type,
            );
          }}
          className={cn(
            "cols entity",
            annotation.type != "token"
              ? "cursor-pointer overflow-clip rounded-md border border-amber-500 bg-amber-100 px-2 text-center after:-mx-2 after:bg-amber-500 after:p-[1px] after:text-center after:text-[10px] after:text-white after:uppercase"
              : "pt-0.5",
            annotation.type != "token" && AnnotationColors[color],
          )}
        >
          {annotation.text}
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
                minSimilarity: 0.7,
                stype: "annotation",
                semantic: true,
                atype: annotation.type,
                q: annotation.text,
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
