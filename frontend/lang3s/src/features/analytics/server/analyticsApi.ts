"use server";
import { getJson, postJson, putJson } from "@/lib/utils/superFetch";
import { PAGE_LIMIT } from "@/features/common/constants";

const BASE_PATH = `${process.env.EMBEDDING_SERVER}/analytics`;

export type AnnotationCountsType = {
  total: number;
  totalPages: number;
  results: [
    {
      content: string;
      path: string;
      value: string;
      document_count: number;
      sentence_count: number;
      mention_count: number;
      mentions_per_document: number;
    },
  ];
};

type EventIntermediate = {
  text: string;
  value: string;
  A0: string[];
  A1: string[];
  TIME: string;
  LOC: string;
  sentence: string;
};

type AnnotationLoaner = {
  entityId: string;
  entityType: string;
  rawScore: number;
  normScore: number;
  category: string;
};

type Cohorts = {
  edges: { id1: string; id2: string; similarity: number }[];
  nodes: { id: string; name: string; support: number; r: number }[];
  clusters: { id: string; name: string; type: string }[];
  id_cid: Record<string, string>;
};

type CohortInformation = {
  edges: {
    source: string;
    sourceId: string;
    target: string;
    targetId: string;
    documentCount: number;
    sentenceCount: number;
  }[];
  ranked: { id: string; support: number }[];
};

type TopicEntity = {
  entity: string;
  type: string;
  count: number;
};

export const topicInformation = async (topic_id: string) => {
  return getJson<TopicEntity>(`${BASE_PATH}/topic/${topic_id}`);
};

export const cohortSupportInformation = async (ids: string[]) => {
  return postJson<CohortInformation>(`${BASE_PATH}/cohortinformation`, {
    ids,
  });
};

export const annotationCounts = async (
  page: number,
  sortBy: "mention_count" | "document_count" | "mentions_per_document",
  mappings: string[],
  filter: string | null | undefined,
) => {
  return postJson<AnnotationCountsType>(`${BASE_PATH}/counts`, {
    mappings,
    page,
    page_size: PAGE_LIMIT,
    order_by: sortBy,
    filter: filter,
  });
};

export const updateAnalytics = async () => {
  return putJson(`${BASE_PATH}/updatestats`);
};

export const cohorts = async () => {
  return postJson<Cohorts>(`${BASE_PATH}/cohorts`);
};

export const annotationAffinity = async (values: string[]) => {
  return postJson<AnnotationLoaner[]>(`${BASE_PATH}/affinity`, {
    values,
  });
};

export const annotationTopicScore = async (values: string[]) => {
  return postJson<AnnotationLoaner[]>(`${BASE_PATH}/topicscore`, {
    values,
  });
};

export const annotationEvents = async (entity: string, value: string) => {
  const results = await postJson<EventIntermediate[]>(`${BASE_PATH}/events`, {
    entity,
    value,
  });

  if (results == null) {
    return [];
  }

  const byValue = results.reduce(
    (agg, d) => {
      if (agg[d.value] == null) {
        agg[d.value] = [];
      }
      agg[d.value].push(d);
      return agg;
    },
    {} as Record<string, EventIntermediate[]>,
  );

  return [
    ...Object.entries(byValue).map(([k, v]) => ({
      value: k,
      count: v.length,
      events: v,
    })),
  ];
};

export const annotationCoOccurrence = async (
  entity: string,
  value: string,
  targets: string[],
) => {
  return postJson<
    {
      e2: string;
      e2Type: string;
      count: number;
    }[]
  >(`${BASE_PATH}/cooccurrence`, {
    entity,
    value,
    targets,
  });
};
