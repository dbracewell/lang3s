"use server";
import { postJson } from "@/lib/utils/superFetch";
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
      count: number;
      docCount: number;
      sentenceCount: number;
      mentionsPerDocument: number;
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
};

export const annotationCounts = async (
  page: number,
  sortBy: string,
  mappings: string[],
) => {
  return postJson<AnnotationCountsType>(`${BASE_PATH}/counts`, {
    mappings,
    page,
    page_size: PAGE_LIMIT,
    order_by: sortBy,
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
