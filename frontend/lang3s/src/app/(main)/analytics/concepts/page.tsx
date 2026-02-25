import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { caller } from "@/lib/trpc/server";
import CircularEdgeBundling from "@/components/charts/CircularEdgeBundling";
import React from "react";

const Page = async () => {
  const data = await caller.analytics.getConceptGraph();
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Corpus Concepts</h1>
        <p className="pageSubheading">
          Groups of entities commonly appearing together in the same documents
        </p>
      </ScrollableBox.Header>
      <CircularEdgeBundling data={data} />
    </ScrollableBox.Container>
  );
};

export default Page;
