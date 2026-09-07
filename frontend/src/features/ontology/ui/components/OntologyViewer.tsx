"use client";
import { OntologySelector } from "@/features/ontology/ui/components/OntologySelector";
import { OntologyViewerInformationPanel } from "@/features/ontology/ui/components/OntologyViewerInformationPanel";
import React from "react";

export const OntologyViewer = ({ path }: { path?: string }) => {
  return (
    <div className="flex h-full min-h-0 w-full flex-1 gap-3">
      <OntologySelector.Provider selectedNode={path}>
        <OntologySelector.SelectedInformation className="scrollable hidden h-full min-h-0 sm:block sm:w-75 lg:w-125">
          <OntologyViewerInformationPanel />
        </OntologySelector.SelectedInformation>
        <div className="flex h-full min-h-full flex-1 flex-col justify-between gap-2 overflow-hidden">
          <OntologySelector.Container orientation="vertical">
            <OntologySelector.BreadCrumbs maxBreadcrumbs={8} />
            <OntologySelector.Sections
              className="text-base"
              sectionWidth={300}
            />
          </OntologySelector.Container>
        </div>
      </OntologySelector.Provider>
    </div>
  );
};
