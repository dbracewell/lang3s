import React from "react";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { OntologyViewer } from "@/features/ontology/ui/components/OntologyViewer";

const OntologyPage = async (props: PageProps<"/system/ontology/viewer">) => {
  const searchParams = await props.searchParams;
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Ontology Viewer</h1>
        <p className="pageSubheading">View and explore the system ontology</p>
      </ScrollableBox.Header>
      <OntologyViewer path={searchParams["path"] as string} />
    </ScrollableBox.Container>
  );
};

export default OntologyPage;
