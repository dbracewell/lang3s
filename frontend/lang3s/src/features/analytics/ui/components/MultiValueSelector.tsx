"use client";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";
import { useTagSearchParams } from "@/features/analytics/hooks";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export const MultiValueSelector = ({
  values,
  currentlySelected,
  className,
  title,
}: {
  values: string[];
  currentlySelected?: string[];
  className?: string;
  title: string;
}) => {
  const [isOpen, setOpen] = useState(false);
  const [selectedValues, setSelectedValues] = useTagSearchParams(
    currentlySelected ?? values,
  );
  const [localValues, setLocalValues] = useState<string[]>(selectedValues);
  useEffect(
    () => setLocalValues(currentlySelected ?? values),
    [currentlySelected, values],
  );

  return (
    <div
      className={cn(
        "relative",
        isOpen && "shadow-shadow rounded-t-2xl shadow-md transition-all",
        className,
      )}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => {
        setOpen(false);
        setLocalValues(selectedValues);
      }}
    >
      <h2
        className={cn(
          "dark:text-foreground rounded-lg rounded-b-none border bg-slate-50 p-1 pl-3 text-sm font-bold text-slate-500 transition-all dark:bg-zinc-600",
          isOpen &&
            "border-slate-800 bg-slate-500 text-white transition-all dark:bg-slate-700",
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
            "flex min-h-8 flex-1 flex-wrap gap-2 border-r bg-white p-2 dark:bg-slate-800",
            isOpen && "bg-slate-50 transition-colors dark:bg-slate-900",
          )}
        >
          {localValues.map((v) => (
            <div
              key={v}
              className="bg-dodger-blue-100 dark:bg-dodger-blue-700 cursor-pointer rounded-2xl border p-1 text-xs"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setLocalValues((p) => p.filter((value) => value !== v));
              }}
            >
              {v}
            </div>
          ))}
        </div>
      </div>
      {isOpen && (
        <div className="animate-dropdown shadow-shadow absolute right-0 left-0 z-10 flex flex-col overflow-clip rounded-lg rounded-t-none border border-t-0 border-slate-800 bg-white p-2 py-4 pb-2 shadow-md dark:bg-zinc-700">
          <div className="grid w-full grid-cols-4 gap-1">
            {values.map((v) => (
              <div
                key={v}
                className="hover:bg-accent flex items-center gap-2 rounded-md p-2"
              >
                <Checkbox
                  id={`entity-${v}`}
                  checked={localValues.includes(v)}
                  onCheckedChange={(e) => {
                    if (e) {
                      setLocalValues((p) => {
                        const a = [...p, v];
                        a.sort();
                        return a;
                      });
                    } else {
                      setLocalValues((p) => p.filter((value) => value !== v));
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
          <Button
            onClick={() => {
              setOpen(false);
              setSelectedValues(localValues);
            }}
          >
            Update
          </Button>
        </div>
      )}
    </div>
  );
};
