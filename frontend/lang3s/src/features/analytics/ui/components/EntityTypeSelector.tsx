"use client";
import { useTagSearchParams } from "@/features/analytics/hooks/useTagSearch";
import { OntologySelectorDialog } from "@/features/ontology/ui/components/OntologySelectorDialog";
import { ChevronDownIcon, ChevronUpIcon, NetworkIcon } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";

export const EntityTypeSelector = ({ values }: { values: string[] }) => {
  const [tags, setTags] = useTagSearchParams(values);
  const [open, setOpen] = useState(false);
  return (
    <div className="relative flex max-h-[300px] min-h-0 flex-col p-2">
      <Button
        variant="ghost"
        className={cn(
          "w-[200px] justify-between border lg:w-[500px]",
          open && "bg-accent rounded-b-none border-b-0",
        )}
        size={"sm"}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
      >
        {tags.length} Selected Type(s)
        {open ? <ChevronUpIcon /> : <ChevronDownIcon />}
      </Button>
      <div
        className={cn(
          "bg-background absolute top-[40px] left-2 z-10 flex h-[150px] w-[200px] flex-1 flex-col gap-1 overflow-hidden border border-t-0 lg:w-[500px]",
          open ? "visible" : "hidden",
        )}
      >
        <OntologySelectorDialog
          rootNode="Entity"
          onSelect={(nodes) => {
            setTags(nodes);
            setOpen(false);
          }}
          defaultCheckedNodes={tags}
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
            {tags.map((tag) => (
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
