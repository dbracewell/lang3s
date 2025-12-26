import { EntitiesPageView } from "@/features/analytics/ui/views/EntitiesPageView";
import {
  createLoader,
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";
import { caller } from "@/lib/trpc/server";

const EntitiesPage = async (props: PageProps<"/analytics/entities">) => {
  const values = await caller.analytics.getUniqueTags({
    annotationType: "entity",
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
    <EntitiesPageView
      sortBy={sortBy}
      filter={!!filter.trim() ? filter.trim() : undefined}
      page={page < 1 ? 1 : page}
      values={values}
    />
  );
};

export default EntitiesPage;
