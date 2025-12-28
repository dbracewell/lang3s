import "server-only";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";
import { MetadataConfiguration, MetadataItem } from "@/features/common/types";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";

export const getMetadata = async () => {
  const data = await logAndRethrow(() =>
    db
      .select({
        source: MetadataTable.source,
        items: jsonAgg(
          jsonBuildObject({
            id: MetadataTable.id,
            name: MetadataTable.name,
            dataType: MetadataTable.dataType,
            formatter: MetadataTable.formatter,
          }),
        ),
      })
      .from(MetadataTable)
      .groupBy(MetadataTable.source),
  );

  const metadataConfig: MetadataConfiguration = {
    document: {},
    annotation: {},
    sentence: {},
  };

  data.forEach((item) => {
    metadataConfig[item.source] = item.items.reduce(
      (agg, m) => {
        agg[m.name] = {
          id: m.id,
          dataType: m.dataType,
          formatter: m.formatter,
        };
        return agg;
      },
      {} as Record<string, MetadataItem>,
    );
  });

  return metadataConfig;
};
