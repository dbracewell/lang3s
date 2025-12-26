import { db } from "@/lib/db";
import { TextAnnotationTable } from "@/lib/db/schema";
import { and, AnyColumn, eq, gt, inArray, lt, or } from "drizzle-orm";
import { coalesce, jsonValue, lower, upper } from "@/lib/db/funcs";
import { randomAlphaUnderscore } from "@/lib/utils/random";

type WithTextAnnotationColumns = {
  textId: AnyColumn;
  start: AnyColumn;
  end: AnyColumn;
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

export const getAnnotationsInSentence = ({
  annotationType,
  textConversion = "upper",
  tags,
  text,
}: {
  annotationType: string;
  textConversion?: "lower" | "upper";
  tags?: string[];
  text?: string;
}) => {
  return db
    .select({
      sentenceAId: TextAnnotationTable.sentenceAid,
      annotationId: TextAnnotationTable.id,
      start: TextAnnotationTable.start,
      end: TextAnnotationTable.end,
      text: (textConversion === "upper"
        ? upper(
            coalesce(
              jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
              TextAnnotationTable.content,
            ),
          )
        : lower(
            coalesce(
              jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
              TextAnnotationTable.content,
            ),
          )
      ).as(randomAlphaUnderscore(10)),
      value: TextAnnotationTable.value,
    })
    .from(TextAnnotationTable)
    .where(
      and(
        eq(TextAnnotationTable.type, annotationType),
        tags ? inArray(TextAnnotationTable.value, tags) : undefined,
        text
          ? eq(upper(TextAnnotationTable.content), text.toUpperCase())
          : undefined,
      ),
    );
};
