import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { PencilIcon, Trash2Icon } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

export const AnnotationTypeValueFormDialog = ({
  defaultValues,
  title,
  onSelect,
}: {
  title: string | React.ReactNode;
  defaultValues: string[];
  onSelect: (values: string[]) => void;
}) => {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<string[]>(defaultValues ?? []);
  const { data: allAnnotationValues, isPending } = useTRPCQuery((trpc) =>
    trpc.system.getAnnotationTypeValueWithMapping.queryOptions(undefined, {
      staleTime: 5 * 60 * 1000,
    }),
  );

  useEffect(() => {
    setValues(defaultValues ?? []);
  }, [defaultValues]);

  const onClose = (value: boolean) => {
    if (value) {
      setOpen(value);
      return;
    }
    setValues([]);
    setOpen(false);
  };

  const onSubmit = () => {
    onSelect(values);
    onClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "icon-xs" })}
      >
        <PencilIcon />
      </DialogTrigger>
      <DialogContent className="h-[450px] overflow-hidden">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Select Annotation Types and Values
          </DialogDescription>
        </DialogHeader>
        <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
          {allAnnotationValues == null || isPending ? (
            <Spinner />
          ) : (
            <div className="grid min-h-0 flex-1 grid-cols-[1fr_1fr] gap-4">
              <AnnotationList
                items={allAnnotationValues}
                values={values}
                onSelect={(v) => setValues((prev) => [...prev, v])}
                hideUsed={true}
              />
              <div className="flex h-full min-h-0 flex-col overflow-clip rounded-lg border">
                <div className="scrollable flex h-full flex-col text-sm">
                  {values.map((annotation) => {
                    return (
                      <div
                        key={annotation}
                        className="bg-row odd:bg-alternate-row flex items-center justify-between gap-2 p-1.5 px-2"
                      >
                        <div className="flex flex-col">{annotation}</div>
                        <Button
                          type="button"
                          variant="destructiveOutline"
                          size="icon-xs"
                          onClick={() => {
                            setValues((prev) =>
                              prev.filter((e) => e !== annotation),
                            );
                          }}
                        >
                          <Trash2Icon />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
        <Button type="button" onClick={onSubmit} className="w-full">
          Save
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export function AnnotationList({
  items,
  hideUsed,
  values,
  onSelect,
}: {
  items: Record<string, string | null>;
  values: string[];
  hideUsed: boolean;
  onSelect: (value: string) => void;
}) {
  return (
    <Command className="rounded-lg border">
      <CommandInput placeholder="Search Annotation..." className="h-9" />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        <CommandGroup>
          {Object.entries(items).map(([value, path]) => {
            if (values.includes(value) || (path != null && hideUsed)) {
              return null;
            }
            return (
              <CommandItem
                key={value}
                value={value}
                onSelect={() => onSelect(value)}
              >
                {value} {path}
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}
