import { TopicsPageView } from "@/modules/analytics/ui/views/TopicsPageView";
import { caller } from "@/trpc/server";
import React from "react";

const TopicsPage = async () => {
  const data = await caller.analytics.getTopics();
  return <TopicsPageView data={data} />;
};

export default TopicsPage;
