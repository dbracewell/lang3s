"use client";

import { CorpusSummary } from "@/features/dashboard/components/CorpusSummary";
import { CorpusStats } from "@/features/dashboard/components/CorpusStats";
import { TopicSummary } from "@/features/dashboard/components/TopicSummary";
import { useQuery } from "@tanstack/react-query";
import { precomputedStatsGetByNameOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { Spinner } from "@/components/Spinner";

type CorpusSummaryType = {
  corpus_summary: string;
  overall_stats: {
    documents: number;
    sentences: number;
    annotations: number;
  };
  topic_summary: { name: string; support: number }[];
};

export const CorpusDetails = () => {
  const {
    data: result,
    isPending,
    error,
  } = useQuery({
    ...precomputedStatsGetByNameOptions({
      client: coreClient,
      path: {
        name: "corpus_summary",
      },
    }),
  });

  if (error) {
    if (
      typeof error.detail !== "string" ||
      !error.detail.toLocaleLowerCase().includes("not found")
    ) {
      throw error;
    }
  }

  if (isPending) {
    return <Spinner />;
  }

  const data = (result?.value as CorpusSummaryType) ?? {};

  return (
    <>
      <CorpusSummary summary={data["corpus_summary"]} />
      <div className="lg:scrollable flex flex-col gap-6 lg:w-1/2">
        <CorpusStats summary={data["overall_stats"]} />
        <TopicSummary summary={data["topic_summary"]} />
      </div>
    </>
  );
};
