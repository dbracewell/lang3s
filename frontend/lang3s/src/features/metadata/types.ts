import { DataType, MetadataSource } from "@/lib/db/schemas/metadata";

export type MetadataItem = {
  id: string;
  dataType: DataType;
  formatter?: string;
  linksToDocumentId: boolean;
  linksToMetadataId: string | null;
  linkedName: string | null;
  linkedSource: string | null;
};

export type MetadataConfiguration = Record<
  MetadataSource,
  Record<string, MetadataItem>
>;
