import { caller } from "@/lib/trpc/server";
import React from "react";
import { TopicsListView } from "@/features/analytics/ui/components/TopicsListView";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { TopicsPageTabs } from "@/features/analytics/ui/components/TopicsPageTabs";
import { TopicsGraph } from "@/features/analytics/ui/components/TopicsGraph";

const TopicsPage = async () => {
  const data = await caller.analytics.getTopics();
  return (
    <ScrollableBox.Container className="gap-3">
      <div className="flex flex-col">
        <h1>Topics</h1>
        <p className="pageSubheading">
          The recurring themes discovered within the corpus
        </p>
      </div>
      <TopicsPageTabs />
      <TopicsListView points={data.points} />
      <TopicsGraph data={data} />
    </ScrollableBox.Container>
  );
};

export default TopicsPage;
