import { caller } from "@/lib/trpc/server";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { EntityTypeSelector } from "@/features/analytics/ui/components/EntityTypeSelector";
import { TopEntitiesList } from "@/features/analytics/ui/components/TopEntitiesList";
import { EntityEvents } from "@/features/analytics/ui/components/EntityEvents";
import { EntityCoOccurrenceVisualization } from "@/features/analytics/ui/components/EntityCoOccurrenceVisualization";
import { ONTOLOGY_ENTITY_ROOT } from "@/features/common/constants";
import { EntityMetrics } from "@/features/analytics/ui/components/EntityMetrics";
import { EntitiesPageTabs } from "@/features/analytics/ui/components/EntitiesPageTabs";

const EntitiesPage = async (props: PageProps<"/analytics/entities">) => {
  const values = await caller.ontology.getFullPath({
    path: ONTOLOGY_ENTITY_ROOT,
  });
  return (
    <ScrollableBox.Container className="relative">
      <ScrollableBox.Header className="flex flex-col items-start gap-y-2 lg:flex-row">
        <div className="flex flex-col">
          <h1>Entities</h1>
          <p className="pageSubheading max-w-sm">
            The entities (real-world objects, e.g. people, places,
            organizations, dates, etc.) mentioned in the corpus
          </p>
        </div>
        <div className="flex w-full flex-1 items-center justify-center">
          <EntityTypeSelector values={values} />
        </div>
      </ScrollableBox.Header>
      <EntitiesPageTabs />
      <EntityEvents />
      <EntityCoOccurrenceVisualization />
    </ScrollableBox.Container>
  );
};

export default EntitiesPage;
