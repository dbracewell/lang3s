import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { ChartSchema } from "@/features/reports/schema";
import { MIN_TOPIC_SIMILARITY } from "@/features/common/constants";
import { DocumentsTable, TextAnnotationTable } from "@/lib/db/schemas/text";
import {
  and,
  asc,
  count,
  countDistinct,
  desc,
  eq,
  ne,
  not,
  sql,
} from "drizzle-orm";
import { db } from "@/lib/db";
import { TopicsTable } from "@/lib/db/schemas/topics";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import {
  Chart,
  CountType,
  DisplayType,
  SeriesSourceType,
} from "@/features/reports/types";
import { MetadataConfiguration, MetadataItem } from "@/features/common/types";
import { getMetadata } from "@/features/common/server/queries";
import { jsonValue } from "@/lib/db/helpers/json";
import { Annotations } from "@/lib/db/annotations";

const LIMIT = 35;

const formatColumn = (
  column: typeof DocumentsTable.metadata | typeof TextAnnotationTable.metadata,
  key: string,
  metadataItem: MetadataItem,
) => {
  let textStatement = jsonValue<string | number>(column, key);
  let valueStatement = jsonValue<string | number>(column, key);

  if (["int", "float"].includes(metadataItem.dataType)) {
    valueStatement = jsonValue<string | number>(
      column,
      key,
      metadataItem.dataType,
    );
  }

  if (metadataItem.formatter != null) {
    if (metadataItem.dataType === "float") {
      valueStatement = sql<number>`ROUND(${jsonValue<number>(column, key, "float")}::numeric, ${metadataItem.formatter}::int)`;
      textStatement = sql<string>`${valueStatement}::text`;
    } else if (metadataItem.dataType === "date") {
      valueStatement = sql<string>`TO_CHAR(${jsonValue<Date>(column, key, "date")}, ${metadataItem.formatter})`;
      textStatement = sql<string>`${valueStatement}`;
    }
  }
  return { textStatement, valueStatement };
};

export const reportsRouter = createTRPCRouter({
  getData: protectedProcedure.input(ChartSchema).query(async ({ input }) => {
    const { x, y, count: countType } = input;
    const metadata = await logAndRethrow(() => getMetadata());

    let finalQuery;

    if (y == null) {
      const q1 = getBaseQuery({
        type: x.type,
        value: x.value ?? "",
        countType,
        metadata,
        displayType: x.display,
      });
      finalQuery = db
        .select({
          text1: q1.text,
          value1: q1.value,
          text2: sql<string>`''`.as(randomAlphaUnderscore()),
          value2: sql<string>`''`.as(randomAlphaUnderscore()),
          documentCount: countDistinct(q1.documentId),
          sentenceCount: countDistinct(q1.sentenceAId),
          mentionCount: count(),
        })
        .from(q1)
        .groupBy((t) => [t.text1, t.value1, t.text2, t.value2])
        .orderBy((t) => [asc(t.text1)]);

      if (["TOPIC", "ANNOTATION"].includes(x.type)) {
        finalQuery = finalQuery.limit(LIMIT);
      }
    } else {
      const q1 = getBaseQuery({
        type: x.type,
        value: x.value ?? "",
        countType,
        metadata,
        displayType: x.display,
      });
      const q2 = getBaseQuery({
        type: y.type,
        value: y.value ?? "",
        countType,
        metadata,
        displayType: y.display,
      });

      const chartType = Chart.getChartType(x.dataType, y.dataType);
      if (chartType === "scatterplot") {
        const query = db
          .select({
            text1: q1.text,
            text2: q2.text,
            value1: q1.value,
            value2: q2.value,
            documentCount: sql<number>`0`,
            sentenceCount: sql<number>`0`,
            mentionCount: sql<number>`0`,
          })
          .from(q1)
          .innerJoin(
            q2,
            and(
              eq(q1.documentId, q2.documentId),
              countType !== "document"
                ? eq(sql`${q1.sentenceAId}`, q2.sentenceAId)
                : undefined,
            ),
          );
        return await logAndRethrow(() => query);
      }
      finalQuery = db
        .select({
          text1: q1.text,
          text2: q2.text,
          value1: q1.value,
          value2: q2.value,
          documentCount: countDistinct(q1.documentId),
          sentenceCount: countDistinct(q1.sentenceAId),
          mentionCount: sql<number>`0`,
        })
        .from(q1)
        .innerJoin(
          q2,
          and(
            eq(q1.documentId, q2.documentId),
            countType !== "document"
              ? eq(sql`${q1.sentenceAId}`, q2.sentenceAId)
              : undefined,
          ),
        )
        .groupBy((t) => [t.text1, t.text2, t.value1, t.value2]);
    }

    if (finalQuery != null) {
      return await logAndRethrow(() => finalQuery);
    }
    return [];
  }),
});

const getTopNTopics = ({ countType }: { countType: CountType }) => {
  return db
    .select({
      topicId: TopicsTable.id,
      name: TopicsTable.name,
      embedding: TopicsTable.embedding,
    })
    .from(TopicsTable)
    .orderBy(
      desc(
        countType === "sentence" ? TopicsTable.support : TopicsTable.documents,
      ),
      asc(TopicsTable.id),
    )
    .limit(LIMIT)
    .as(randomAlphaUnderscore());
};

const getTopNAnnotations = ({
  value,
  countType,
  displayType,
}: {
  value: string;
  countType: CountType;
  displayType: DisplayType;
}) => {
  const base = Annotations.getAnnotationsWithOntology({
    options: { normalize: true },
    computedColumns: (o) => ({
      value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
    }),
    limitTo: value
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean),
    annotationFields: ["sentenceAid", "documentId"],
  }).as(randomAlphaUnderscore());

  return db
    .select({
      text: Chart.convertToDisplay({
        content: base.content,
        value: base.value,
        displayType,
        isValue: false,
      }).as(randomAlphaUnderscore()),
      value: Chart.convertToDisplay({
        content: base.content,
        value: base.value,
        displayType,
        isValue: true,
      }).as(randomAlphaUnderscore()),
      documentCount: countDistinct(base.documentId),
      sentenceCount: countDistinct(base.sentenceAid),
      mentionCount: count(),
    })
    .from(base)
    .groupBy((t) => [t.text, t.value])
    .orderBy((t) => [desc(Chart.getCountColumn(countType, t)), asc(t.text)])
    .limit(LIMIT)
    .as(randomAlphaUnderscore());
};

const getBaseQuery = ({
  type,
  value,
  countType,
  metadata,
  displayType,
}: {
  type: SeriesSourceType;
  value: string;
  countType: CountType;
  metadata: MetadataConfiguration;
  displayType: DisplayType;
}) => {
  switch (type) {
    case "ANNOTATION":
      const topNAnnotations = getTopNAnnotations({
        value,
        countType,
        displayType,
      });

      const base = Annotations.getAnnotationsWithOntology({
        options: { normalize: true },
        computedColumns: (o) => ({
          value: sql<string>`${o.name}`.as(randomAlphaUnderscore()),
        }),
        limitTo: value
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        annotationFields: ["sentenceAid", "documentId"],
      }).as(randomAlphaUnderscore());

      return db
        .select({
          sentenceAId: base.sentenceAid,
          documentId: base.documentId,
          text: topNAnnotations.text,
          value: sql<number | string>`0`.as(randomAlphaUnderscore()),
        })
        .from(base)
        .innerJoin(
          topNAnnotations,
          and(
            eq(
              Chart.convertToDisplay({
                content: base.content,
                value: base.value,
                displayType,
                isValue: false,
              }),
              topNAnnotations.text,
            ),
            eq(
              Chart.convertToDisplay({
                content: base.content,
                value: base.value,
                displayType,
                isValue: true,
              }),
              topNAnnotations.value,
            ),
          ),
        )
        .as(randomAlphaUnderscore());

    case "TOPIC":
      const topNTopics = getTopNTopics({ countType });
      const baseSentence = Annotations.getSentences().as(
        randomAlphaUnderscore(),
      );
      return db
        .selectDistinct({
          sentenceAId: baseSentence.sentenceAid,
          documentId: baseSentence.documentId,
          text: topNTopics.name,
          value: sql<number | string>`0`.as(randomAlphaUnderscore()),
        })
        .from(topNTopics)
        .innerJoin(
          baseSentence,
          sql<number>`(1 - (${baseSentence.embedding} <=> ${topNTopics.embedding})) >= ${MIN_TOPIC_SIMILARITY}`,
        )
        .as(randomAlphaUnderscore());

    case "ANNOTATION_METADATA":
      const { textStatement: aTextStmt, valueStatement: aValueStmt } =
        formatColumn(
          TextAnnotationTable.metadata,
          value,
          metadata["annotation"][value],
        );
      return db
        .select({
          sentenceAId: TextAnnotationTable.sentenceAid,
          documentId: TextAnnotationTable.documentId,
          text: aTextStmt.as(randomAlphaUnderscore()),
          value: aValueStmt.as(randomAlphaUnderscore()),
        })
        .from(TextAnnotationTable)
        .where(
          and(
            ne(TextAnnotationTable.type, "sentence"),
            not(
              sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
            ),
          ),
        )
        .orderBy((t) => t.value)
        .as(randomAlphaUnderscore());

    case "SENTENCE_METADATA":
      const { textStatement: sTextStmt, valueStatement: sValueStmt } =
        formatColumn(
          TextAnnotationTable.metadata,
          value,
          metadata["sentence"][value],
        );
      return db
        .select({
          sentenceAId: TextAnnotationTable.sentenceAid,
          documentId: TextAnnotationTable.documentId,
          text: sTextStmt.as(randomAlphaUnderscore()),
          value: sValueStmt.as(randomAlphaUnderscore()),
        })
        .from(TextAnnotationTable)
        .where(
          and(
            eq(TextAnnotationTable.type, "sentence"),
            not(
              sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
            ),
          ),
        )
        .orderBy((t) => t.value)
        .as(randomAlphaUnderscore());

    case "DOCUMENT_METADATA":
      const { textStatement: dTextStmt, valueStatement: dValueStmt } =
        formatColumn(
          DocumentsTable.metadata,
          value,
          metadata["document"][value],
        );
      return db
        .select({
          sentenceAId: sql<string>`' '`.as(randomAlphaUnderscore()),
          documentId: DocumentsTable.id,
          text: dTextStmt.as(randomAlphaUnderscore()),
          value: dValueStmt.as(randomAlphaUnderscore()),
        })
        .from(DocumentsTable)
        .orderBy((t) => t.value)
        .as(randomAlphaUnderscore());
  }
};
