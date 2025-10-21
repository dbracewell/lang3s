import { db } from "@/db";
import { TextAnnotationTable } from "@/db/schema";
import {
  and,
  AnyColumn,
  Column,
  eq,
  getTableColumns,
  gt,
  inArray,
  lt,
  or,
  SQL,
  sql,
  SQLWrapper,
  Table,
  type SelectedFields,
} from "drizzle-orm";

export const metadataSelect = <T>(
  field: string,
  sqlType: "int" | "float" | "varchar",
): SQL.Aliased<T> => {
  switch (sqlType) {
    case "int":
      return sql<T>`(metadata->>${field})::int`.as(field);
    case "float":
      return sql<T>`(metadata->>${field})::numeric`.as(field);
    default:
      return sql<T>`(metadata->>${field})::varchar`.as(field);
  }
};

type WithTextAnnotationColumns = {
  textId: AnyColumn;
  start: AnyColumn;
  end: AnyColumn;
};
const __overlaps = <T extends WithTextAnnotationColumns>(t1: T, t2: T) => {
  return and(
    eq(t1.textId, t2.textId),
    lt(t1.start, t2.end),
    gt(t1.end, t2.start),
  );
};

export const overlaps = (t1: unknown, t2: unknown) => {
  return __overlaps(
    t1 as WithTextAnnotationColumns,
    t2 as WithTextAnnotationColumns,
  );
};

const __notOverlaps = <T extends WithTextAnnotationColumns>(t1: T, t2: T) => {
  return and(
    eq(t1.textId, t2.textId),
    or(gt(t1.start, t2.end), lt(t1.end, t2.start)),
  );
};

export const notOverlaps = (t1: unknown, t2: unknown) => {
  return __notOverlaps(
    t1 as WithTextAnnotationColumns,
    t2 as WithTextAnnotationColumns,
  );
};

export const selectTextAnnotations = <T extends Record<string, any>>({
  annotationType,
  columns,
  tags,
  text,
}: {
  annotationType: string;
  columns: T;
  tags?: string[];
  text?: string;
}) => {
  return db
    .select(columns)
    .from(TextAnnotationTable)
    .where(
      and(
        eq(TextAnnotationTable.type, annotationType),
        tags ? inArray(TextAnnotationTable.value, tags) : undefined,
        text
          ? eq(sql`upper(${TextAnnotationTable.text})`, text.toUpperCase())
          : undefined,
      ),
    );
};

export function randomAlphaUnderscore(length: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_";
  let result = "";
  for (let i = 0; i < length; i++) {
    const idx = Math.floor(Math.random() * chars.length);
    result += chars[idx];
  }
  return result;
}

export const getAnnotationsInSentence = ({
  annotationType,
  textConversion,
  tags,
  text,
}: {
  annotationType: string;
  textConversion?: "lower" | "upper";
  tags?: string[];
  text?: string;
}) => {
  const s1 = selectTextAnnotations({
    annotationType: "sentence",
    columns: {
      sentenceId: TextAnnotationTable.id,
      start: TextAnnotationTable.start,
      end: TextAnnotationTable.end,
      textId: TextAnnotationTable.textId,
    },
  }).as("s1");
  const other = selectTextAnnotations({
    annotationType,
    tags,
    text,
    columns: {
      id: TextAnnotationTable.id,
      start: TextAnnotationTable.start,
      end: TextAnnotationTable.end,
      textId: TextAnnotationTable.textId,
      text:
        textConversion == null
          ? TextAnnotationTable.text
          : textConversion === "lower"
            ? sql<string>`lower(${TextAnnotationTable.text})`.as("text")
            : sql<string>`upper(${TextAnnotationTable.text})`.as("text"),
      value: TextAnnotationTable.value,
    },
  }).as("other");

  const prefix = randomAlphaUnderscore(5);
  return db
    .select({
      textId: sql<string>`${s1.textId}`.as(prefix + "textId"),
      sentenceId: sql<string>`${s1.sentenceId}`.as(prefix + "sentenceId"),
      text: sql<string>`${other.text}`.as(prefix + "text"),
      value: sql<string>`${other.value}`.as(prefix + "value"),
      annotationId: sql<string>`${other.id}`.as(prefix + "annotationId"),
      start: sql<number>`${other.start}`.as(prefix + "start"),
      end: sql<number>`${other.end}`.as(prefix + "end"),
    })
    .from(s1)
    .innerJoin(other, overlaps(s1, other));
};
