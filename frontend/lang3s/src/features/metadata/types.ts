import { DataType } from "@/features/common/types";

export const MetadataSources = ["document", "annotation", "sentence"] as const;
export type MetadataSource = (typeof MetadataSources)[number];

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
