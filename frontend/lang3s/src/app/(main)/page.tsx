import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { CorpusDetails } from "@/features/dashboard/components/CorpusDetails";

export default async function Home() {
  return (
    <ScrollableBox.Container className="m-1">
      <ScrollableBox.Header>
        <h1>Corpus Summary</h1>
      </ScrollableBox.Header>
      <ScrollableBox.ScrollArea
        outerClassName="rounded-none! border-0!"
        className="flex min-h-0 w-full flex-1 flex-col gap-6 lg:h-full lg:flex-row"
      >
        <CorpusDetails />
      </ScrollableBox.ScrollArea>
    </ScrollableBox.Container>
  );
}
