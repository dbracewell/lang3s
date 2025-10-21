import { MultiValueSelector } from "@/modules/analytics/ui/components/MultiValueSelector";
import { EntityNetwork } from "@/modules/analytics/ui/views/EntitiesPageView/EntityNetwork";
import { TopEntitiesList } from "@/modules/analytics/ui/views/EntitiesPageView/TopEntitiesList";
import { caller } from "@/trpc/server";

export const EntitiesPageView = async () => {
  const values = await caller.analytics.getUniqueTags({
    annotationType: "entity",
  });

  return (
    <div className="relative flex h-full w-full flex-1 flex-col gap-6 overflow-hidden">
      <MultiValueSelector
        values={values}
        title="Entity Types"
        className="mx-auto w-full max-w-2xl"
      />
      <TopEntitiesList values={values} />
      <EntityNetwork values={values} />
    </div>
  );
};
