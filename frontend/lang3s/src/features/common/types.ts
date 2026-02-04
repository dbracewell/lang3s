import { UserRole } from "@/lib/auth/permissions";
import { DataType } from "@/lib/db/schemas/metadata";

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

export type DataTypeNameToTypeMap = {
  [K in DataType]: K extends "int" | "float"
    ? number
    : K extends "boolean"
      ? boolean
      : K extends "date" | "datetime"
        ? Date
        : string; // default to string
};

export const DataTypeCategories = [
  "string",
  "number",
  "date",
  "boolean",
] as const;

export type DataTypeCategory = (typeof DataTypeCategories)[number];

export const DataTypeNameToCategoryMap: Record<DataType, DataTypeCategory> = {
  string: "string",
  "string[]": "string",
  int: "number",
  float: "number",
  boolean: "boolean",
  date: "date",
};

export const DataTypeFilterNames = [
  "select",
  "numeric-range",
  "date-range",
] as const;
export type DataTypeFilter = (typeof DataTypeFilterNames)[number];

export const DataTypeNameToFilterMap: Record<DataTypeCategory, DataTypeFilter> =
  {
    string: "select",
    number: "numeric-range",
    date: "date-range",
    boolean: "select",
  };
