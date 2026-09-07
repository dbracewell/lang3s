"use client";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useQueryState } from "nuqs";
import { parseAsInteger } from "nuqs/server";
import { XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/Spinner";
import { useEffect } from "react";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { type CohortClusterEntry } from "@/clients/analytics";
import { useQuery } from "@tanstack/react-query";
import { cohortInformationOptions } from "@/clients/analytics/@tanstack/react-query.gen";
import { analyticsClient } from "@/lib/api";

export const CohortView = ({ cohort }: { cohort: CohortClusterEntry[] }) => {
  const [, setSelectedCohort] = useQueryState(
    "c",
    parseAsInteger.withDefault(-1).withOptions({ clearOnDefault: true }),
  );
  const { setContext } = useChatContext();

  const { data, isPending, isError, error } = useQuery({
    ...cohortInformationOptions({
      client: analyticsClient,
      body: {
        ids: cohort.map((c) => c.id),
      },
    }),
  });

  useEffect(() => {
    if (data != null) {
      setContext(
        data.ranked
          .map((r) => r.id.split("-").slice(0, -1).join("-"))
          .join("\n"),
      );
    }
  }, [data, setContext]);

  if (isError) {
    throw error;
  }

  return (
    <Card className="animate-zoomin absolute top-0 left-0 z-10 h-full w-full overflow-hidden">
      <CardHeader>
        <CardTitle className="text-2xl">
          Cohort View{" "}
          <span className="text-dodger-blue-500">{cohort[0].name}</span>
        </CardTitle>
        <CardDescription>
          {cohort.length} entities mentioned together in the same documents
        </CardDescription>
        <CardAction>
          <Button variant="ghost" onClick={() => setSelectedCohort(-1)}>
            <XIcon />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        {isPending ? (
          <Spinner />
        ) : (
          <div className="flex min-h-0 flex-1 flex-col overflow-clip rounded-lg border">
            <div className="flex flex-col gap-2 p-2">
              <h2 className="text-lg font-semibold">Central Entities</h2>
              <div className="flex gap-2">
                {data?.ranked.slice(0, 3).map((r, i) => (
                  <div
                    key={i}
                    className="border-dodger-blue-400 border-r px-4 font-light first:pl-0 last:border-r-0"
                  >
                    {r.id.split("-").slice(0, -1).join("-")}
                  </div>
                ))}
              </div>
            </div>
            <h2 className="p-2 text-lg font-semibold">Co-occurrence counts</h2>
            <div className="scrollable w-full flex-1">
              <table className="w-full">
                <thead>
                  <tr className="bg-heading sticky top-0 left-0 text-white">
                    <th className="px-2 py-1 text-center" colSpan={2}>
                      Entities
                    </th>
                    <th className="px-2 py-1 text-left">Documents in common</th>
                    <th className="px-2 py-1 text-left">Sentences in common</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.edges.map((r) => (
                    <tr
                      key={`${r.sourceId}-${r.targetId}`}
                      className="bg-row odd:bg-alternate-row"
                    >
                      <td className="px-2 py-1">{r.source}</td>
                      <td className="px-2 py-1">{r.target}</td>
                      <td className="px-2 py-1">{r.documentCount}</td>
                      <td className="px-2 py-1">{r.sentenceCount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
