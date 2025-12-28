"use client";
import React from "react";
import {
  OntologySelector,
  Section,
} from "@/features/ontology/ui/components/OntologySelector";
import { buttonVariants } from "@/components/ui/button";
import { OntologyEditorInformationPanel } from "@/features/ontology/ui/components/OntologyEditorInformationPanel";
import { AddConceptDialog } from "@/features/ontology/ui/components/AddConceptDialog";
import { DeleteConceptButton } from "@/features/ontology/ui/components/DeleteConceptButton";

export const OntologyEditor = ({ selectedNode }: { selectedNode?: string }) => {
  return (
    <div className="flex h-full min-h-0 w-full flex-1 gap-3">
      <OntologySelector.Provider rootNode="ALL" selectedNode={selectedNode}>
        <OntologySelector.SelectedInformation className="scrollable hidden h-full min-h-0 sm:block sm:w-[300px] lg:w-[500px]">
          <OntologyEditorInformationPanel />
        </OntologySelector.SelectedInformation>
        <div className="flex h-full min-h-full flex-1 flex-col justify-between gap-2 overflow-hidden">
          <OntologySelector.Container orientation="vertical">
            <OntologySelector.BreadCrumbs maxBreadcrumbs={8} />
            <OntologySelector.Sections
              className="text-base"
              sectionWidth={300}
              sectionFooter={sectionFooter}
              entryToolButtons={[entryDeleteButton]}
              entryAlternativeNextButton={entryAddButton}
            />
          </OntologySelector.Container>
        </div>
      </OntologySelector.Provider>
    </div>
  );
};

const sectionFooter = (section: Section) => {
  const pathParts = section[0].path.split(".");
  const parentPath = pathParts.slice(0, pathParts.length - 1).join(".");
  return (
    <div className="px-2 py-2">
      <AddConceptDialog
        parentId={section[0].parentId}
        parentPath={parentPath}
        triggerClassName={buttonVariants({
          variant: "outline",
          size: "sm",
          className: "w-full",
        })}
      />
    </div>
  );
};

const entryAddButton = (item: Section[number]) => (
  <AddConceptDialog
    parentId={item.id}
    parentPath={item.path}
    triggerClassName={buttonVariants({
      variant: "ghost",
      size: "icon-xs",
    })}
  />
);

const entryDeleteButton = (item: Section[number]) => {
  if (item.path.split(".").length == 2) return null;
  return <DeleteConceptButton path={item.path} />;
};
