"use client";
import { MultiValueSelector } from "@/features/analytics/ui/components/MultiValueSelector";
import { EntityNetwork } from "@/features/analytics/ui/views/EntitiesPageView/EntityNetwork";
import { TopEntitiesList } from "@/features/analytics/ui/views/EntitiesPageView/TopEntitiesList";
import { EntityEvents } from "@/features/analytics/ui/views/EntitiesPageView/EntityEvents";
import { useTagSearchParams } from "@/features/analytics/hooks";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

export const defaultValues = [
  "FAC",
  "GPE",
  "LAW",
  "LOC",
  "NORP",
  "ORG",
  "PERSON",
  "PRODUCT",
  "WORK_OF_ART",
];

export const EntitiesPageView = ({
  page,
  sortBy,
  filter,
  values,
}: {
  page: number;
  sortBy: string;
  filter?: string;
  values: string[];
}) => {
  const [tags] = useTagSearchParams(defaultValues);

  return (
    <div className="relative flex h-full w-full flex-1 flex-col gap-6 overflow-hidden">
      <div className="flex flex-col items-start gap-y-2 lg:flex-row">
        <div className="flex flex-col">
          <h1>Entities</h1>
          <p className="pageSubheading">The unique entities </p>
        </div>
        <MultiValueSelector
          values={values}
          currentlySelected={tags}
          title="Entity Types"
          className="mx-auto w-full max-w-2xl flex-1"
        />
      </div>
      <TopEntitiesList
        values={tags}
        page={page}
        filter={filter}
        sortBy={sortBy}
      />
      <EntityEvents />
      <EntityNetwork values={tags} />
    </div>
  );
};
