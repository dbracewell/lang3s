"use client";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { EntityTypeSelector } from "@/features/analytics/ui/components/EntityTypeSelector";
import { EntityEvents } from "@/features/analytics/ui/components/EntityEvents";
import { EntityCoOccurrenceVisualization } from "@/features/analytics/ui/components/EntityCoOccurrenceVisualization";
import { ONTOLOGY_ENTITY_ROOT } from "@/features/common/constants";
import { EntitiesPageTabs } from "@/features/analytics/ui/components/EntitiesPageTabs";
import { useQuery } from "@tanstack/react-query";
import { ontologyGetNodePathOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

const EntitiesPage = () => {
  const { data: values } = useQuery({
    ...ontologyGetNodePathOptions({
      client: coreClient,
      path: {
        path: ONTOLOGY_ENTITY_ROOT,
      },
    }),
  });

  return (
    <ScrollableBox.Container className="relative m-1">
      <ScrollableBox.Header className="flex flex-col items-start gap-y-2 lg:flex-row">
        <div className="flex flex-col">
          <h1>Entities</h1>
          <p className="pageSubheading max-w-sm">
            The entities (real-world objects, e.g. people, places,
            organizations, dates, etc.) mentioned in the corpus
          </p>
        </div>
        <div className="flex w-full flex-1 items-center justify-center">
          {values == null ? (
            <Skeleton className="h-10 w-20" />
          ) : (
            <EntityTypeSelector values={values} />
          )}
        </div>
      </ScrollableBox.Header>
      <EntitiesPageTabs />
      <EntityEvents />
      <EntityCoOccurrenceVisualization />
    </ScrollableBox.Container>
  );
};

export default EntitiesPage;
