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
  isNotNull,
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
import { getMetadata } from "@/features/common/server/queries";
import { jsonValue } from "@/lib/db/helpers/json";
import { Annotations, matchPath } from "@/lib/db/annotations";
import { MetadataConfiguration, MetadataItem } from "@/features/metadata/types";
import { AnnotationWithOntologyView, TopicSentences } from "@/lib/db/schema";

const LIMIT = 35;

export const reportsRouter = createTRPCRouter({
  getData: protectedProcedure.input(ChartSchema).query(async ({ input }) => {
    const { x, y, count: countType } = input;
    const metadata = await logAndRethrow(() => getMetadata());

    const q1 = getBaseQuery({
      type: x.type,
      value: x.value ?? "",
      countType,
      metadata,
    });

    return await logAndRethrow(() => {
      if (y == null) {
        return db
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
      }

      const q2 = getBaseQuery({
        type: y.type,
        value: y.value ?? "",
        countType,
        metadata,
      });

      const chartType = Chart.getChartType(x.dataType, y.dataType);

      if (chartType === "scatterplot") {
        return db
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
      }

      return db
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
    });
  }),
});

const getBaseQuery = ({
  type,
  value,
  countType,
  metadata,
}: {
  type: SeriesSourceType;
  value: string;
  countType: CountType;
  metadata: MetadataConfiguration;
}) => {
  switch (type) {
    case "ANNOTATION":
      return getAnnotations({
        page: 1,
        countType,
        value,
      });

    case "TOPIC":
      return getTopics({
        page: 1,
        countType,
        value,
      });

    case "ANNOTATION_METADATA":
      return getAnnotationMetadata({
        page: 1,
        value,
        metadata,
        isSentence: false,
      });

    case "SENTENCE_METADATA":
      return getAnnotationMetadata({
        page: 1,
        value,
        metadata,
        isSentence: true,
      });

    case "DOCUMENT_METADATA":
      return getDocumentMetadata({
        page: 1,
        value,
        metadata,
      });
  }
};

const getAnnotations = ({
  page,
  value,
  countType,
}: {
  page: number;
  value: string;
  countType: CountType;
}) => {
  const paths = value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

  const entityStats = db
    .select({
      content:
        sql`${AnnotationWithOntologyView.normalized} || ' (' || ${AnnotationWithOntologyView.name} || ')'`.as(
          randomAlphaUnderscore(),
        ),
      docCount: countDistinct(AnnotationWithOntologyView.documentId).as(
        randomAlphaUnderscore(),
      ),
    })
    .from(AnnotationWithOntologyView)
    .where(matchPath(AnnotationWithOntologyView.path, paths))
    .groupBy(
      AnnotationWithOntologyView.normalized,
      AnnotationWithOntologyView.name,
    )
    .orderBy((t) => desc(t.docCount))
    .offset((page - 1) * LIMIT)
    .limit(LIMIT)
    .as(randomAlphaUnderscore());

  return db
    .select({
      sentenceAId: AnnotationWithOntologyView.sentenceAid,
      documentId: AnnotationWithOntologyView.documentId,
      text: entityStats.content,
      value: sql<string>`${entityStats.content}`.as(randomAlphaUnderscore()),
    })
    .from(AnnotationWithOntologyView)
    .innerJoin(
      entityStats,
      eq(
        sql`${AnnotationWithOntologyView.normalized} || ' (' || ${AnnotationWithOntologyView.name} || ')'`,
        entityStats.content,
      ),
    )
    .orderBy(desc(entityStats.docCount), asc(entityStats.content))
    .as(randomAlphaUnderscore());
};

const getTopics = ({
  page,
  value,
  countType,
}: {
  page: number;
  value: string;
  countType: CountType;
}) => {
  const topNTopics = db
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
    .offset((page - 1) * LIMIT)
    .limit(LIMIT)
    .as(randomAlphaUnderscore());

  return db
    .selectDistinct({
      sentenceAId: TopicSentences.sentenceAid,
      documentId: TopicSentences.documentId,
      text: topNTopics.name,
      value: sql<number | string>`0`.as(randomAlphaUnderscore()),
    })
    .from(topNTopics)
    .innerJoin(TopicSentences, eq(TopicSentences.topicId, topNTopics.topicId))
    .as(randomAlphaUnderscore());
};

const getDocumentMetadata = ({
  page,
  value,
  metadata,
}: {
  page: number;
  value: string;
  metadata: MetadataConfiguration;
}) => {
  const { textStatement: dTextStmt, valueStatement: dValueStmt } = formatColumn(
    DocumentsTable.metadata,
    value,
    metadata["document"][value],
  );

  let pageData = null;
  if (["date", "datetime"].includes(metadata["document"][value].dataType)) {
    pageData = db
      .select({
        value: dValueStmt.as(randomAlphaUnderscore()),
      })
      .from(DocumentsTable)
      .orderBy((t) => t.value)
      .offset((page - 1) * LIMIT)
      .limit(LIMIT)
      .as(randomAlphaUnderscore());
  } else {
    pageData = db
      .select({
        value: dValueStmt.as(randomAlphaUnderscore()),
        count: count().as(randomAlphaUnderscore()),
      })
      .from(DocumentsTable)
      .groupBy((t) => t.value)
      .orderBy((t) => [desc(t.count), t.value])
      .offset((page - 1) * LIMIT)
      .limit(LIMIT)
      .as(randomAlphaUnderscore());
  }

  const base = db
    .select({
      documentId: DocumentsTable.id,
      text: dTextStmt.as(randomAlphaUnderscore()),
      value: dValueStmt.as(randomAlphaUnderscore()),
    })
    .from(DocumentsTable)
    .as(randomAlphaUnderscore());

  return db
    .select({
      sentenceAId: sql<string>`' '`.as(randomAlphaUnderscore()),
      documentId: base.documentId,
      text: base.text,
      value: base.value,
    })
    .from(base)
    .innerJoin(pageData, eq(pageData.value, base.value))
    .orderBy((t) => t.value)
    .as(randomAlphaUnderscore());
};

const getAnnotationMetadata = ({
  page,
  value,
  metadata,
  isSentence,
}: {
  page: number;
  value: string;
  metadata: MetadataConfiguration;
  isSentence: boolean;
}) => {
  const { textStatement: dTextStmt, valueStatement: dValueStmt } = formatColumn(
    TextAnnotationTable.metadata,
    value,
    metadata["document"][value],
  );

  let pageData = null;
  if (["date", "datetime"].includes(metadata["document"][value].dataType)) {
    pageData = db
      .select({
        value: dValueStmt.as(randomAlphaUnderscore()),
      })
      .from(TextAnnotationTable)
      .where(
        and(
          Annotations.isNotStopword,
          isSentence ? Annotations.isSentence : undefined,
          isNotNull(dValueStmt),
        ),
      )
      .orderBy((t) => t.value)
      .offset((page - 1) * LIMIT)
      .limit(LIMIT)
      .as(randomAlphaUnderscore());
  } else {
    pageData = db
      .select({
        value: dValueStmt.as(randomAlphaUnderscore()),
        count: count().as(randomAlphaUnderscore()),
      })
      .from(TextAnnotationTable)
      .where(
        and(
          Annotations.isNotStopword,
          isSentence ? Annotations.isSentence : undefined,
          isNotNull(dValueStmt),
        ),
      )
      .groupBy((t) => t.value)
      .orderBy((t) => [desc(t.count), t.value])
      .offset((page - 1) * LIMIT)
      .limit(LIMIT)
      .as(randomAlphaUnderscore());
  }

  const base = db
    .select({
      sentenceAId: TextAnnotationTable.sentenceAid,
      documentId: TextAnnotationTable.documentId,
      text: dTextStmt.as(randomAlphaUnderscore()),
      value: dValueStmt.as(randomAlphaUnderscore()),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        Annotations.isNotStopword,
        isSentence ? Annotations.isSentence : undefined,
        isNotNull(dValueStmt),
      ),
    )
    .as(randomAlphaUnderscore());

  return db
    .select({
      sentenceAId: base.sentenceAId,
      documentId: base.documentId,
      text: base.text,
      value: base.value,
    })
    .from(base)
    .innerJoin(pageData, eq(pageData.value, base.value))
    .orderBy((t) => t.value)
    .as(randomAlphaUnderscore());
};

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

  if (metadataItem.dataType === "string[]") {
    return {
      textStatement: sql<string>`jsonb_array_elements((${column}->>${key})::jsonb)`,
      valueStatement: sql<string>`jsonb_array_elements((${column}->>${key})::jsonb)`,
    };
  }

  if (metadataItem.formatter != null) {
    if (metadataItem.dataType === "float") {
      valueStatement = sql<number>`ROUND(${jsonValue<number>(column, key, "float")}::numeric, ${metadataItem.formatter}::int)`;
      textStatement = sql<string>`${valueStatement}::text`;
    } else if (["date", "datetime"].includes(metadataItem.dataType)) {
      valueStatement = sql<string>`TO_CHAR(${jsonValue<Date>(column, key, "date")}, ${metadataItem.formatter})`;
      textStatement = sql<string>`${valueStatement}`;
    }
  }
  return { textStatement, valueStatement };
};
