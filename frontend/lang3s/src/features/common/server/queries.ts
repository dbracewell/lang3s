import "server-only";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { MetadataSource, MetadataTable } from "@/lib/db/schemas/metadata";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";
import { MetadataConfiguration, MetadataItem } from "@/features/metadata/types";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { and, eq, inArray, sql } from "drizzle-orm";

export const getMetadataBySourceAndName = async (
  source: MetadataSource,
  names: string[],
) => {
  const lowerNames = names.map((name) => name.toLowerCase());

  return await logAndRethrow(() => {
    return db
      .select()
      .from(MetadataTable)
      .where(
        and(
          eq(MetadataTable.source, source),
          inArray(sql`LOWER(${MetadataTable.name})`, lowerNames),
        ),
      );
  });
};

export const getMetadata = async () => {
  const data = await logAndRethrow(() => {
    const selfJoin = db
      .select()
      .from(MetadataTable)
      .as(randomAlphaUnderscore());
    return db
      .select({
        source: MetadataTable.source,
        items: jsonAgg(
          jsonBuildObject({
            id: MetadataTable.id,
            name: MetadataTable.name,
            dataType: MetadataTable.dataType,
            formatter: MetadataTable.formatter,
            linksToDocumentId: MetadataTable.linksToDocumentId,
            linksToMetadataId: MetadataTable.linksToMetadataId,
            linkedName: selfJoin.name,
            linkedSource: selfJoin.source,
          }),
        ),
      })
      .from(MetadataTable)
      .leftJoin(selfJoin, eq(MetadataTable.linksToMetadataId, selfJoin.id))
      .groupBy(MetadataTable.source);
  });

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
          linksToDocumentId: m.linksToDocumentId,
          linksToMetadataId: m.linksToMetadataId,
          linkedName: m.linkedName,
          linkedSource: m.linkedSource,
        };
        return agg;
      },
      {} as Record<string, MetadataItem>,
    );
  });

  return metadataConfig;
};
