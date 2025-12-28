"use client";
import React from "react";
import {
  OntologySelector,
  Section,
} from "@/components/ontology/OntologySelector";
import { buttonVariants } from "@/components/ui/button";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { EditorPanel } from "@/features/ontology/ui/views/OntologyEditorPageView/EditorPanel";
import { AddConceptDialog } from "@/features/ontology/ui/views/OntologyEditorPageView/AddConceptDialog";
import { DeleteConceptButton } from "@/features/ontology/ui/views/OntologyEditorPageView/DeleteConceptButton";

export const OntologyEditorPageView = ({
  selectedNode,
}: {
  selectedNode?: string;
}) => {
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Ontology Editor</h1>
        <p className="pageSubheading">Edit the system Ontology.</p>
      </ScrollableBox.Header>
      <div className="flex h-full min-h-0 w-full flex-1 gap-3">
        <OntologySelector.Provider rootNode="ALL" selectedNode={selectedNode}>
          <OntologySelector.SelectedInformation className="scrollable hidden h-full min-h-0 sm:block sm:w-[300px] lg:w-[500px]">
            <EditorPanel />
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
    </ScrollableBox.Container>
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
