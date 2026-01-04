import { UserRole } from "@/lib/auth/permissions";

export type BasicUserInfo = {
  id: string;
  role: UserRole;
  name: string;
  username: string;
};

export type FullUserInfo = BasicUserInfo & {
  name: string;
  email: string;
  keys?: { id: string; name?: string; key: string }[];
};

export const DATA_TYPE_CATEGORIES = [
  "categorical",
  "number",
  "date",
  "timestamp",
] as const;
export type DataTypeCategory = (typeof DATA_TYPE_CATEGORIES)[number];
export const DATA_TYPES = [
  "string",
  "int",
  "float",
  "boolean",
  "date",
  "datetime",
] as const;
export type DataType = (typeof DATA_TYPES)[number];

export const DataTypeCategoryMap: Record<DataType, DataTypeCategory> = {
  string: "categorical",
  date: "date",
  boolean: "categorical",
  datetime: "timestamp",
  int: "number",
  float: "number",
} as const;

export const METADATA_SOURCES = ["document", "annotation", "sentence"] as const;
export type MetadataSourceType = (typeof METADATA_SOURCES)[number];

export type MetadataItem = {
  id: string;
  dataType: DataType;
  formatter?: string;
};

export type MetadataConfiguration = Record<
  MetadataSourceType,
  Record<string, MetadataItem>
>;
