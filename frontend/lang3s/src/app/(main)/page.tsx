import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { CorpusSummary } from "@/features/precomputed/components/CorpusSummary";
import { caller } from "@/lib/trpc/server";
import { TopicSummary } from "@/features/precomputed/components/TopicSummary";
import { CorpusStats } from "@/features/precomputed/components/CorpusStats";

type CorpusSummaryType = {
  corpus_summary: string;
  overall_stats: {
    documents: number;
    sentences: number;
    annotations: number;
  };
  topic_summary: { name: string; support: number }[];
};

export default async function Home() {
  const data = (await caller.precomputedStats.get({
    name: "corpus_summary",
  })) as CorpusSummaryType;

  return (
    <ScrollableBox.Container className="m-1">
      <ScrollableBox.Header>
        <h1>Corpus Summary</h1>
      </ScrollableBox.Header>
      <div className="flex min-h-0 w-full flex-1 flex-col gap-6 lg:flex-row">
        <CorpusSummary summary={data["corpus_summary"]} />
        <div className="scrollable flex w-1/2 flex-col gap-6">
          <CorpusStats summary={data["overall_stats"]} />
          <TopicSummary summary={data["topic_summary"]} />
        </div>
      </div>
    </ScrollableBox.Container>
  );
}
