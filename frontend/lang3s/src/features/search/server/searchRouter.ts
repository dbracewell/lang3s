import { SearchParamSchema } from "@/features/search/schemas";
import {
  annotationSearch,
  docSearch,
  topicSearch,
} from "@/features/search/server/searchStrategies";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import {
  SEARCH_ANNOTATION_CASED_THRESHOLD,
  SEARCH_ANNOTATION_UNCASED_THRESHOLD,
  SEARCH_DOCUMENT_CASED_THRESHOLD,
  SEARCH_DOCUMENT_UNCASED_THRESHOLD,
  SEARCH_TOPIC_CASED_THRESHOLD,
  SEARCH_TOPIC_UNCASED_THRESHOLD,
} from "@/features/common/constants";
import {
  AnnotationSearchResult,
  DocumentSearchResult,
  SearchResults,
  TopicSearchResult,
} from "@/features/search/types";
import { getCachedSearchParams } from "@/features/search/server/paramsCache";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { Annotations } from "@/lib/db/annotations";
import { and, inArray } from "drizzle-orm";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { TopicsTable } from "@/lib/db/schemas/topics";
import { db } from "@/lib/db";

export const SearchRouter = createTRPCRouter({
  searchDocuments: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const params = await getCachedSearchParams(input);

      if (params == null) {
        return {
          results: [],
          total: 0,
          entities: [],
          type: "document",
          nextCursor: undefined,
        } as SearchResults<DocumentSearchResult>;
      }

      const { embedding, query, page, isStrict, hasCase } = params;
      return (await docSearch({
        embedding,
        threshold: hasCase
          ? SEARCH_DOCUMENT_CASED_THRESHOLD
          : SEARCH_DOCUMENT_UNCASED_THRESHOLD,
        query,
        isStrict,
        page,
      })) as SearchResults<DocumentSearchResult>;
    }),

  searchAnnotations: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const params = await getCachedSearchParams(input);

      if (params == null) {
        return {
          results: [],
          total: 0,
          nextCursor: undefined,
        } as SearchResults<AnnotationSearchResult>;
      }

      const { embedding, query, page, isStrict, hasCase } = params;
      return await logAndRethrow(() =>
        annotationSearch({
          embedding,
          threshold: hasCase
            ? SEARCH_ANNOTATION_CASED_THRESHOLD
            : SEARCH_ANNOTATION_UNCASED_THRESHOLD,
          query,
          isStrict,
          page,
        }),
      );
    }),

  searchTopics: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const params = await getCachedSearchParams(input);

      if (params == null) {
        return {
          results: [],
          total: 0,
          nextCursor: undefined,
        } as SearchResults<TopicSearchResult>;
      }

      const { embedding, query, page, isStrict, hasCase } = params;
      return await logAndRethrow(() =>
        topicSearch({
          embedding,
          threshold: hasCase
            ? SEARCH_TOPIC_CASED_THRESHOLD
            : SEARCH_TOPIC_UNCASED_THRESHOLD,
          query,
          isStrict,
          page,
        }),
      );
    }),

  searchParameters: protectedProcedure
    .input(SearchParamSchema)
    .query(async ({ input }) => {
      const { q, aid, sid, tid, isStrict } = input;

      const [annotations, sentences, topics] = await logAndRethrow(() =>
        Promise.all([
          aid && aid.length > 0
            ? Annotations.getAnnotationsWithOntology({
                options: { normalize: true },
                annotationFields: ["id"],
              }).where(inArray(TextAnnotationTable.id, aid))
            : ([] as { content: string; id: string }[]),
          sid && sid.length > 0
            ? Annotations.getAnnotationsWithOntology({
                options: { normalize: false },
                annotationFields: ["id"],
              }).where(
                and(
                  inArray(TextAnnotationTable.id, sid),
                  Annotations.isSentence,
                ),
              )
            : ([] as { content: string; id: string }[]),
          tid && tid.length > 0
            ? db
                .select({ id: TopicsTable.id, name: TopicsTable.name })
                .from(TopicsTable)
                .where(inArray(TopicsTable.id, tid))
            : ([] as { name: string; id: string }[]),
        ]),
      );

      return {
        annotations: annotations,
        sentences: sentences,
        topics: topics,
        query: q?.trim() ?? undefined,
        isStrict: isStrict == null ? false : isStrict,
      };
    }),
});
