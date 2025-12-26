"use client";
import React from "react";
import { OntologySelector } from "@/components/ontology/OntologySelector";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { ExtraInformation } from "@/features/ontology/ui/views/OntologyPageView/ExtraInformation";

export const OntologyPageView = ({
  selectedNode,
}: {
  selectedNode?: string;
}) => {
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Ontology Viewer</h1>
        <p className="pageSubheading">View and explore the system Ontology.</p>
      </ScrollableBox.Header>
      <div className="flex h-full min-h-0 w-full flex-1 gap-3">
        <OntologySelector.Provider rootNode="ALL" selectedNode={selectedNode}>
          <OntologySelector.SelectedInformation className="scrollable hidden h-full min-h-0 sm:block sm:w-[300px] lg:w-[500px]">
            <ExtraInformation />
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
    </ScrollableBox.Container>
  );
};
