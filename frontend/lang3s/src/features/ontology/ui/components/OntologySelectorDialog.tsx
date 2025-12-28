import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { OntologySelector } from "@/features/ontology/ui/components/OntologySelector";
import React, { useEffect, useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { NetworkIcon } from "lucide-react";
import type { VariantProps } from "class-variance-authority";

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
  useEffect(() => {
    setCheckedNodes(defaultCheckedNodes ?? []);
  }, [defaultCheckedNodes]);
  return (
    <Dialog open={open ?? isOpen} onOpenChange={onOpenChange ?? setIsOpen}>
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
                    (onOpenChange ?? setIsOpen)(false);
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
