"use client";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useTagSearchParams } from "@/modules/analytics/hooks";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useState } from "react";

export const MultiValueSelector = ({
  values,
  className,
  title,
}: {
  values: string[];
  className?: string;
  title: string;
}) => {
  const [isOpen, setOpen] = useState(false);
  const [selectedValues, setSelectedValues] = useTagSearchParams(values);
  return (
    <div
      className={cn(
        "relative",
        isOpen && "rounded-t-2xl shadow transition-all",
        className,
      )}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <h2
        className={cn(
          "rounded-lg rounded-b-none border bg-slate-50 p-1 pl-3 text-sm font-bold text-slate-500 transition-all",
          isOpen && "border-slate-800 bg-slate-500 text-white transition-all",
        )}
      >
        {title}
      </h2>
      <div
        className={cn(
          "flex items-center justify-between overflow-clip rounded-2xl rounded-t-none border border-t-0 bg-neutral-200 transition-all",
          isOpen && "rounded-b-none! border-slate-800 transition-all",
        )}
      >
        <div
          className={cn(
            "flex min-h-8 flex-1 flex-wrap gap-2 border-r bg-white p-2",
            isOpen && "bg-slate-50 transition-colors",
          )}
        >
          {selectedValues.map((v) => (
            <div
              key={v}
              className="bg-dodger-blue-100 cursor-pointer rounded-2xl border p-1 text-xs"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setSelectedValues((p) => p.filter((value) => value !== v));
              }}
            >
              {v}
            </div>
          ))}
        </div>
      </div>
      {isOpen && (
        <div className="animate-dropdown absolute right-0 left-0 z-10 flex overflow-clip rounded-lg rounded-t-none border border-t-0 border-slate-800 bg-white p-2 py-4">
          <div className="grid w-full grid-cols-4 gap-1">
            {values.map((v) => (
              <div
                key={v}
                className="hover:bg-accent flex items-center gap-2 rounded-md p-2"
              >
                <Checkbox
                  id={`entity-${v}`}
                  checked={selectedValues.includes(v)}
                  onCheckedChange={(e) => {
                    if (e) {
                      setSelectedValues((p) => {
                        const a = [...p, v];
                        a.sort();
                        return a;
                      });
                    } else {
                      setSelectedValues((p) =>
                        p.filter((value) => value !== v),
                      );
                    }
                  }}
                />
                <Label
                  htmlFor={`entity-${v}`}
                  className="flex-1 cursor-pointer truncate"
                >
                  {v}
                </Label>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
