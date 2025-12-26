import { TopicsPageView } from "@/features/topics/ui/views/TopicsPageView";
import { caller } from "@/lib/trpc/server";
import React from "react";

const TopicsPage = async () => {
  const data = await caller.topics.getTopics();
  return <TopicsPageView data={data} />;
};

export default TopicsPage;
