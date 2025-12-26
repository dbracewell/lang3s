import { TopicIdPageView } from "@/features/topics/ui/views/TopicIdPageView";
import { caller } from "@/lib/trpc/server";

const Page = async (props: PageProps<"/analytics/topics/[id]">) => {
  const { id } = await props.params;
  const data = await caller.topics.getTopic({ id });
  return <TopicIdPageView data={data} />;
};
export default Page;
