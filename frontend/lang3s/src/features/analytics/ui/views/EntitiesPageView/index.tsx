import { MultiValueSelector } from "@/features/analytics/ui/components/MultiValueSelector";
import { EntityNetwork } from "@/features/analytics/ui/views/EntitiesPageView/EntityNetwork";
import { TopEntitiesList } from "@/features/analytics/ui/views/EntitiesPageView/TopEntitiesList";
import { caller } from "@/lib/trpc/server";
import { EntityEvents } from "@/features/analytics/ui/views/EntitiesPageView/EntityEvents";

export const EntitiesPageView = async () => {
  const values = await caller.analytics.getUniqueTags({
    annotationType: "entity",
  });
  const defaultValues = [
    "FAC",
    "GPE",
    "LAW",
    "NORP",
    "ORG",
    "PERSON",
    "PRODUCT",
    "WORK_OF_ART",
  ];
  return (
    <div className="relative flex h-full w-full flex-1 flex-col gap-6 overflow-hidden">
      <MultiValueSelector
        values={values}
        defaultValues={defaultValues}
        title="Entity Types"
        className="mx-auto w-full max-w-2xl"
      />
      <TopEntitiesList values={values} defaultValues={defaultValues} />
      <EntityEvents />
      <EntityNetwork values={values} />
    </div>
  );
};
