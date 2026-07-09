"use client";
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
import { Spinner } from "@/components/Spinner";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useQuery } from "@tanstack/react-query";
import { ontologyGetPotentialMappingsOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";

export const AnnotationTypeValueFormDialog = ({
  defaultValues,
  title,
  onSelectAction,
}: {
  title: string | React.ReactNode;
  defaultValues: string[];
  onSelectAction: (values: string[]) => void;
}) => {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<string[]>(defaultValues ?? []);

  const { data: allAnnotationValues, isPending } = useQuery({
    ...ontologyGetPotentialMappingsOptions({
      client: coreClient,
    }),
  });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setValues(defaultValues ?? []);
  }, [defaultValues, setValues]);

  const onClose = (value: boolean) => {
    if (value) {
      setOpen(value);
      return;
    }
    setValues([]);
    setOpen(false);
  };

  const onSubmit = () => {
    onSelectAction(values);
    onClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "icon-xs" })}
      >
        <PencilIcon />
      </DialogTrigger>
      <DialogContent className="h-112.5 overflow-hidden">
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
                items={allAnnotationValues.items}
                values={values}
                onSelectAction={(v) => setValues((prev) => [...prev, v])}
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
  onSelectAction,
}: {
  items: Record<string, unknown>;
  values: string[];
  hideUsed: boolean;
  onSelectAction: (value: string) => void;
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
                onSelect={() => onSelectAction(value)}
              >
                {value} {path as string}
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}
