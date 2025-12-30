"use client";
import { OntologySelectorDialog } from "@/features/ontology/ui/components/OntologySelectorDialog";
import { ChevronDownIcon, ChevronUpIcon, NetworkIcon } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useEntitySearchParams } from "@/features/analytics/hooks/useEntitySearchParams";
import useClickOutside from "@/hooks/useClickOutside";
import { ONTOLOGY_ENTITY_ROOT } from "@/features/common/constants";

export const EntityTypeSelector = ({ values }: { values: string[] }) => {
  const [params, setParams] = useEntitySearchParams();
  const [open, setOpen] = useState(false);
  const goodTags = useMemo(() => {
    return params.tags.filter((tag) => values.includes(tag));
  }, [values, params.tags]);
  const router = useRouter();
  const divRef = useRef<HTMLDivElement>(null);

  useClickOutside([divRef], () => {
    setOpen(false);
  });

  return (
    <div
      className="relative flex max-h-[300px] min-h-0 flex-col p-2"
      ref={divRef}
    >
      <Button
        variant="ghost"
        className={cn(
          "w-[200px] justify-between border lg:w-[500px]",
          open &&
            "bg-accent rounded-b-none border-b-0 border-slate-900 transition-all duration-100 ease-linear",
        )}
        size={"sm"}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
      >
        {goodTags.length} Selected Type(s)
        {open ? <ChevronUpIcon /> : <ChevronDownIcon />}
      </Button>
      <div
        className={cn(
          "bg-background absolute top-10 left-2 z-10 flex h-[150px] w-[200px] flex-1 flex-col gap-1 overflow-hidden border border-t-0 lg:w-[500px]",
          open
            ? "animate-accordion-down visible border-slate-900 duration-100"
            : "animate-accordion-up hidden duration-100",
        )}
      >
        <OntologySelectorDialog
          rootNode={ONTOLOGY_ENTITY_ROOT}
          onSelect={(nodes) => {
            setParams({
              tags: nodes,
              page: 1,
            });
            setOpen(false);
            router.refresh();
          }}
          defaultCheckedNodes={params.tags}
          trigger={
            <div className="flex items-center gap-2">
              <NetworkIcon /> Ontology Selector
            </div>
          }
          variant="listButton"
          size="icon-sm"
          className="w-full rounded-none border-0 bg-slate-700 text-xs"
        />
        <div className="scrollable h-full min-h-0 min-w-full flex-1 flex-col gap-1">
          <div className="flex min-h-0 w-fit min-w-full flex-col">
            {goodTags.map((tag) => (
              <div
                key={tag}
                className="bg-row odd:bg-alternate-row p-1 text-sm"
              >
                {tag}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
