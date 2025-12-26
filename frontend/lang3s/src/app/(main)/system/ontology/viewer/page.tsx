import { OntologyPageView } from "@/features/ontology/ui/views/OntologyPageView";
import React from "react";

const OntologyPage = async (props: PageProps<"/system/ontology/viewer">) => {
  const searchParams = await props.searchParams;
  return <OntologyPageView selectedNode={searchParams["path"] as string} />;
};

export default OntologyPage;
