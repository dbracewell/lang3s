import { pgEnum, pgTable, text, unique, uuid } from "drizzle-orm/pg-core";
import { DATA_TYPES, METADATA_SOURCES } from "@/features/common/types";

export const metadataSourceEnum = pgEnum("metadata_sources", METADATA_SOURCES);
export const metadataDataTypeEnum = pgEnum("metadata_data_type", DATA_TYPES);

export const MetadataTable = pgTable(
  "metadata",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    source: metadataSourceEnum("source").notNull(),
    name: text("name").notNull(),
    dataType: metadataDataTypeEnum("data_type").notNull(),
    formatter: text("formatter"),
  },
  (t) => [unique("source_name_unique").on(t.source, t.name)],
);
