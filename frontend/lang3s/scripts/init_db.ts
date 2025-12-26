import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";

await db
  .insert(MetadataTable)
  .values([
    {
      source: "document",
      name: "language",
      dataType: "string",
    },
    {
      source: "document",
      name: "mime-type",
      dataType: "string",
    },
  ])
  .execute();
