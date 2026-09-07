import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { OntologySelector } from "@/features/ontology/ui/components/OntologySelector";
import type { VariantProps } from "class-variance-authority";
import { NetworkIcon } from "lucide-react";
import React, { useState } from "react";

type OntologySelectorDialogProps = {
  open?: boolean;
  onOpenChange?: (value: boolean) => void;
  rootNode?: string;
  trigger?: React.ReactNode;
  defaultCheckedNodes?: string[];
  className?: string;
  onSelect?: (values: string[]) => void;
} & VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

export const DefaultOntologyTrigger = () => {
  return (
    <>
      <NetworkIcon /> Ontology Selector
    </>
  );
};

export const OntologySelectorDialog = ({
  open,
  onOpenChange,
  rootNode,
  trigger,
  onSelect,
  defaultCheckedNodes,
  variant,
  className,
  size,
  asChild,
}: OntologySelectorDialogProps) => {
  const [isOpen, setIsOpen] = useState(open ?? false);
  const [checkedNodes, setCheckedNodes] = useState<string[]>(
    defaultCheckedNodes ?? [],
  );

  const isControlled = open !== undefined;
  const effectiveOpen = isControlled ? open : isOpen;

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setCheckedNodes(defaultCheckedNodes ?? []);
    }

    if (!isControlled) {
      setIsOpen(nextOpen);
    }

    onOpenChange?.(nextOpen);
  };

  return (
    <Dialog open={effectiveOpen} onOpenChange={handleOpenChange}>
      {trigger && (
        <DialogTrigger
          className={buttonVariants({ variant, size, className })}
          asChild={asChild}
        >
          {trigger}
        </DialogTrigger>
      )}
      <DialogContent className="scrollable flex h-full w-full max-w-full! flex-col sm:h-[90%] lg:max-w-[770px]!">
        <DialogHeader>
          <DialogTitle>Ontology Selector</DialogTitle>
          <DialogDescription className="sr-only">
            Select the ontology elements to use.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 w-full flex-1 flex-col justify-between gap-2">
          <OntologySelector.Provider
            rootNode={rootNode}
            checkedNodes={onSelect ? checkedNodes : undefined}
            setCheckedNodes={onSelect ? setCheckedNodes : undefined}
          >
            <OntologySelector.Container>
              <OntologySelector.BreadCrumbs />
              <OntologySelector.Sections />
              <OntologySelector.SelectedInformation
                className="min-w-full p-1!"
                showPath={false}
                showName={false}
              />
              <OntologySelector.SelectionSummary />
              {onSelect && (
                <Button
                  type="button"
                  onClick={() => {
                    handleOpenChange(false);
                    onSelect(checkedNodes);
                  }}
                >
                  Select
                </Button>
              )}
            </OntologySelector.Container>
          </OntologySelector.Provider>
        </div>
      </DialogContent>
    </Dialog>
  );
};
