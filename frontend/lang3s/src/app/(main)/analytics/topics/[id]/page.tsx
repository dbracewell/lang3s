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
import React from "react";
import { TopicIdContext } from "@/features/analytics/ui/components/TopicIdContext";

const Page = async (props: PageProps<"/analytics/topics/[id]">) => {
  const { id } = await props.params;
  const data = await caller.analytics.getTopic({ id });
  return (
    <>
      <TopicIdContext
        sentences={data.sentences.map((s) => s.content)}
        entities={data.entities}
      />
      <Card className="animate-zoomin flex flex-1 flex-col gap-2 overflow-hidden">
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
        <CardContent className="flex min-h-0 flex-col overflow-hidden p-2!">
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 text-sm md:grid-cols-[2fr_0.5fr]">
            <SentenceSection sentences={data.sentences} />
            <EntitySection entities={data.entities} />
          </div>
        </CardContent>
      </Card>
    </>
  );
};
export default Page;

const SentenceSection = ({
  sentences,
}: {
  sentences: { content: string }[];
}) => {
  return (
    <div className="flex h-full min-h-0 flex-col gap-1">
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
    <div className="flex h-full min-h-0 flex-col gap-1">
      <h2 className="mb-2 text-center text-xl font-semibold">Top Entities</h2>
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
