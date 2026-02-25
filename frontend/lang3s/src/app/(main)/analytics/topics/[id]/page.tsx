import { caller } from "@/lib/trpc/server";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GoBackButton } from "@/components/buttons/GoBackButton";
import { CircleQuestionMarkIcon, XIcon } from "lucide-react";
import { Hint } from "@/components/hint";
import React, { Suspense, useMemo } from "react";
import { TopicIdContext } from "@/features/analytics/ui/components/TopicIdContext";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/Spinner";
import { cn } from "@/lib/utils/cn";

const Page = async (props: PageProps<"/analytics/topics/[id]">) => {
  const { id } = await props.params;
  return (
    <Suspense fallback={<Spinner />}>
      <SuspensedPage id={id} />
    </Suspense>
  );
};

const SuspensedPage = async ({ id }: { id: string }) => {
  const data = await caller.analytics.getTopic({ id });
  return (
    <>
      <TopicIdContext
        sentences={data.sentences.map((s) => s.content)}
        entities={data.entities}
      />
      <Card className="animate-zoomin m-1 flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
        <CardHeader>
          <CardTitle>
            <h1 className="">
              Topic <span className="text-dodger-blue-500">{data.name}</span>
            </h1>
          </CardTitle>
          <CardDescription>
            <h2 className="text-muted-foreground text-md pb-5">
              {new Intl.NumberFormat().format(data.sentenceCount)} sentences
              across {new Intl.NumberFormat().format(data.documentCount)}{" "}
              documents.
            </h2>
          </CardDescription>
          <CardAction>
            <GoBackButton variant="ghost">
              <XIcon />
            </GoBackButton>
          </CardAction>
        </CardHeader>
        <CardContent className="scrollable flex flex-col p-2!">
          <div className="flex min-h-0 flex-1 flex-col gap-6 text-sm md:flex-row">
            <div className="flex flex-1 flex-col gap-y-6">
              <KeywordSection keywords={data.keywords} />
              <SentenceSection sentences={data.sentences} />
            </div>
            <EntitySection entities={data.entities} />
          </div>
        </CardContent>
      </Card>
    </>
  );
};
export default Page;

const KeywordSection = ({
  keywords,
}: {
  keywords: { category: string | null; count: number }[];
}) => {
  const normalizer = useMemo(
    () => Math.max(...keywords.map((k) => k.count)),
    [keywords],
  );
  const r = useMemo(
    () => keywords.sort((a, b) => Math.random() - Math.random()),
    [keywords],
  );
  return (
    <div className="flex flex-col gap-1">
      <h2 className="pb-2 text-xl font-semibold">
        Top {keywords.length} concepts
      </h2>
      <div className="bg-muted/40 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border p-4">
        {r.map((k, i) => (
          <div
            key={k.category}
            className={cn(
              "text-sm lowercase",
              i % 2 === 0 ? "text-dodger-blue-500" : "text-muted-foreground",
            )}
            style={{
              fontSize: `${Math.max(14, Math.ceil((k.count / normalizer) * 28))}px`,
            }}
          >
            {k.category}
          </div>
        ))}
      </div>
    </div>
  );
};

const SentenceSection = ({
  sentences,
}: {
  sentences: { content: string; similarity: number }[];
}) => {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-1">
      <h2 className="pb-2 text-xl font-semibold">
        Top {sentences.length} topic sentences
      </h2>
      <div className="flex min-h-0 flex-1 flex-col overflow-clip rounded-lg border">
        <div className="scrollable flex flex-col gap-1">
          {sentences.map((sentence, index) => (
            <div key={index} className="bg-row odd:bg-alternate-row p-2">
              {sentence.content}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const EntitySection = ({
  entities,
}: {
  entities: {
    entity: string;
    type: string;
    count: number;
  }[];
}) => {
  return (
    <div className="flex h-full flex-col gap-1 md:max-w-80">
      <h2 className="mb-2 text-xl font-semibold">Top Entities</h2>
      <div className="flex min-h-0 flex-1 flex-col overflow-clip rounded-lg border">
        <div className="scrollable flex flex-col gap-1">
          <table className="w-full">
            <thead className="sticky top-0">
              <tr className="bg-heading text-white">
                <th className="py-1 pl-4 text-left">Entity</th>
                <th className="flex items-center gap-1 py-1 pr-4">
                  Mentions
                  <Hint
                    hint={`Number of times this entity is mentioned\n(Includes multiple mentions per document.)`}
                  >
                    <CircleQuestionMarkIcon className="size-3" />
                  </Hint>
                </th>
              </tr>
            </thead>
            <tbody>
              {entities.map((entity) => (
                <tr
                  key={`${entity.type}-${entity.entity}`}
                  className="bg-row odd:bg-alternate-row"
                >
                  <td className="w-[65%] py-1 pl-4">
                    {entity.entity}{" "}
                    <span className="text-muted-foreground text-xs">
                      {" "}
                      ({entity.type})
                    </span>
                  </td>
                  <td className="py-1 pr-4 text-center">{entity.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
