// src/server/services/global-embedding-cache.ts
import { LRUCache } from "lru-cache";
import { ParsedSearchParams } from "@/features/search/schemas";
import { SearchParams } from "@/features/search/server/searchStrategies";
import { logAndRethrow, tryCatch } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { inArray } from "drizzle-orm";
import { TopicsTable } from "@/lib/db/schemas/topics";
import { t3env } from "@/lib/t3env";

type Return = Promise<
  (Omit<SearchParams, "threshold"> & { hasCase: boolean }) | undefined
>;

const embeddingCache = new LRUCache<string, Return>({
  max: 1000,
  ttl: 1000 * 60 * 60,
});

export const getCachedSearchParams = async (params: ParsedSearchParams) => {
  const stringified = JSON.stringify(params);
  if (!embeddingCache.has(stringified)) {
    const promise = getFinalSearchParameters(params).catch((err) => {
      embeddingCache.delete(stringified);
      throw err;
    });
    embeddingCache.set(stringified, promise);
  }
  return embeddingCache.get(stringified)!;
};

const addEmbeddings = (e1: number[], e2: number[]) => {
  for (let i = 0; i < e1.length; i++) {
    e1[i] += e2[i];
  }
};

const getFinalSearchParameters = async (params: ParsedSearchParams): Return => {
  const { q, aid, sid, tid, cursor, isStrict } = params;
  let embedding: number[] | undefined = undefined;
  let embeddingCount = 0;
  let finalQuery: string = q?.trim() ?? "";
  let finalPage: number = Math.max(1, cursor ?? 1);
  let finalIsStrict: boolean = isStrict == null ? false : isStrict;

  //Get the annotation embedding if an annotation id is provided
  if (aid != null) {
    const annotations = await logAndRethrow(() =>
      db
        .select({
          embedding: TextAnnotationTable.embedding,
          text: TextAnnotationTable.content,
        })
        .from(TextAnnotationTable)
        .where(inArray(TextAnnotationTable.id, aid)),
    );
    if (annotations.length > 0) {
      embedding = annotations[0].embedding;
      embeddingCount = 1;
      for (let i = 1; i < annotations.length; i++) {
        addEmbeddings(embedding, annotations[i].embedding);
        embeddingCount++;
      }
    }
  }

  //Get the topic embedding if a topic is provided
  if (tid != null) {
    const topics = await logAndRethrow(() =>
      db
        .select({
          embedding: TopicsTable.embedding,
        })
        .from(TopicsTable)
        .where(inArray(TopicsTable.id, tid)),
    );
    if (topics.length > 0) {
      if (embedding == null) {
        embedding = topics[0].embedding;
      } else {
        addEmbeddings(embedding, topics[0].embedding);
      }
      embeddingCount = 1;
      for (let i = 1; i < topics.length; i++) {
        addEmbeddings(embedding, topics[i].embedding);
        embeddingCount++;
      }
    }
  }

  if (sid != null) {
    const sentences = await logAndRethrow(() =>
      db
        .select({
          embedding: TextAnnotationTable.embedding,
        })
        .from(TextAnnotationTable)
        .where(inArray(TextAnnotationTable.id, sid)),
    );
    if (sentences.length > 0) {
      if (embedding == null) {
        embedding = sentences[0].embedding;
      } else {
        addEmbeddings(embedding, sentences[0].embedding);
      }
      embeddingCount = 1;
      for (let i = 1; i < sentences.length; i++) {
        addEmbeddings(embedding, sentences[i].embedding);
        embeddingCount++;
      }
    }
  }

  //If we have no embeddings, but have a query, and are not in strict mode
  //Embed the query
  if (embeddingCount === 0 && !!q && !finalIsStrict) {
    const { data: res, isError } = await tryCatch(
      fetch(`${t3env.EMBEDDING_SERVER}/embed`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: finalQuery,
        }),
      }),
    );
    if (!isError && res.ok) {
      embedding = (await res.json()) as number[];
      embeddingCount += 1;
    }
  } else if (!q && embeddingCount === 0) {
    return undefined;
  }

  if (embeddingCount > 1 && embedding != null) {
    for (let i = 0; i < embedding.length; i++) {
      embedding[i] /= embeddingCount;
    }
  }

  let hasCase = true;
  if (
    embeddingCount === 0 &&
    !!q &&
    finalQuery.toLowerCase() === finalQuery &&
    finalQuery.toUpperCase() === finalQuery
  ) {
    hasCase = false;
  }

  return {
    embedding,
    query: finalQuery,
    isStrict: finalIsStrict,
    page: finalPage,
    hasCase,
  };
};
