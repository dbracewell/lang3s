import React from "react";
import { TopicInfoPage } from "@/features/analytics/ui/components/TopicInfoPage";

const Page = async (props: PageProps<"/analytics/topics/[id]">) => {
  const { id } = await props.params;
  return <TopicInfoPage id={Number(id)} />;
};

export default Page;
