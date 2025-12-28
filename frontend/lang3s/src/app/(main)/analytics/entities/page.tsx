import {
  createLoader,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";
import { caller } from "@/lib/trpc/server";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { EntityTypeSelector } from "@/features/analytics/ui/components/EntityTypeSelector";
import { TopEntitiesList } from "@/features/analytics/ui/components/TopEntitiesList";
import { EntityEvents } from "@/features/analytics/ui/components/EntityEvents";
import { EntityCoOccurrenceVisualization } from "@/features/analytics/ui/components/EntityCoOccurrenceVisualization";

const EntitiesPage = async (props: PageProps<"/analytics/entities">) => {
  const values = await caller.ontology.getFullPath({
    path: "ALL.Entity",
  });
  const loader = createLoader({
    page: parseAsInteger.withDefault(1).withOptions({ clearOnDefault: true }),
    sortBy: parseAsStringEnum([
      "mentions",
      "docs",
      "mentionsPerDoc",
    ]).withDefault("mentions"),
    filter: parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  });

  const { page, sortBy, filter } = await loader(props.searchParams);
  return (
    <ScrollableBox.Container className="relative">
      <ScrollableBox.Header className="flex flex-col items-start gap-y-2 lg:flex-row">
        <div className="flex flex-col">
          <h1>Entities</h1>
          <p className="pageSubheading">The unique entities </p>
        </div>
        <div className="flex w-full flex-1 items-center justify-center">
          <EntityTypeSelector values={values} />
        </div>
      </ScrollableBox.Header>
      <TopEntitiesList
        allValues={values}
        page={page}
        filter={filter}
        sortBy={sortBy}
      />
      <EntityEvents />
      <EntityCoOccurrenceVisualization allValues={values} />
    </ScrollableBox.Container>
  );
};

export default EntitiesPage;
