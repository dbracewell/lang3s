import {
  boolean,
  index,
  pgEnum,
  pgTable,
  text,
  unique,
  uuid,
} from "drizzle-orm/pg-core";
import { type DataTypeNameToTypeMap } from "@/features/common/types";
import { type SQL, sql, type SQLWrapper } from "drizzle-orm";
import { jsonValue } from "@/lib/db/helpers/json";

export const MetadataSources = ["document", "annotation", "sentence"] as const;
export type MetadataSource = (typeof MetadataSources)[number];

export const DataTypeNames = [
  "string",
  "string[]",
  "int",
  "float",
  "boolean",
  "date",
  "datetime",
] as const;
export type DataType = (typeof DataTypeNames)[number];

export const metadataSourceEnum = pgEnum("metadata_sources", MetadataSources);
export const metadataDataTypeEnum = pgEnum("metadata_data_type", DataTypeNames);

export const MetadataTable = pgTable(
  "metadata",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    source: metadataSourceEnum("source").notNull(),
    name: text("name").notNull(),
    dataType: metadataDataTypeEnum("data_type").notNull(),
    formatter: text("formatter"),
    linksToDocumentId: boolean("links_to_document_id").default(false).notNull(),
    linksToMetadataId: uuid("metadata_link"),
  },
  (t) => [
    unique("source_name_unique").on(t.source, t.name),
    index("metadata_link_index").on(t.linksToMetadataId),
  ],
);

export const getMetadataValue = <K extends DataType>({
  metadataColumn,
  metadataKey,
  metadataType,
}: {
  metadataColumn: SQLWrapper;
  metadataKey: string;
  metadataType: K;
}): SQL<DataTypeNameToTypeMap[K]> => {
  if (metadataType === "string[]") {
    return sql<
      DataTypeNameToTypeMap[K]
    >`json_each(${metadataColumn}->>'${metadataKey}')`;
  }
  return jsonValue<DataTypeNameToTypeMap[K]>(
    metadataColumn,
    metadataType,
    metadataType,
  );
};
