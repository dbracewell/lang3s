import { ReadonlyURLSearchParams } from "next/navigation";
import {
  Lang3sQueryType,
  ParsedSearchParams,
  QueryTypes,
} from "@/features/search/params";

export const toSearchParams = (searchParams: ParsedSearchParams) => {
  const params = new URLSearchParams();

  Object.entries(searchParams).forEach(([k, v]) => {
    if (v == null) return;
    if (typeof v === "string") {
      if (!!v.trim()) {
        params.set(k, String(v));
      }
    } else if (typeof v === "boolean" && v) {
      params.set(k, String(v));
    } else if (typeof v === "number" && v != 0) {
      params.set(k, String(v));
    } else {
      params.set(k, String(v));
    }
  });

  // if (!!searchParams.q?.trim()) {
  //   params.set("q", searchParams.q.trim());
  // }
  // if (!!searchParams.aid?.trim()) {
  //   params.set("aid", searchParams.aid.trim());
  // }
  // if (searchParams.atype === "annotation" && !!searchParams.atype?.trim()) {
  //   params.set("atype", searchParams.atype.trim());
  // }
  // if (searchParams.semantic && !!searchParams.minSimilarity) {
  //   params.set("minSimilarity", String(searchParams.minSimilarity));
  // }
  //
  // if (searchParams.semantic) {
  //   params.set("semantic", String(true));
  // }
  //
  // if (searchParams.stype) {
  //   params.set("type", searchParams.stype);
  // }
  //
  // if (!!searchParams.page) {
  //   params.set("page", String(searchParams.page));
  // }

  return params.toString();
};

export const parseUrlSearchParams = (
  searchParams: ReadonlyURLSearchParams,
): ParsedSearchParams => {
  const data: Record<string, string | string[] | undefined> = {};
  searchParams.keys().forEach((k) => {
    data[k] = searchParams.get(k) ?? undefined;
  });
  return parseSearchParams(data);
};

export const parseSearchParams = (
  searchParams: Record<string, string | string[] | undefined>,
): ParsedSearchParams => {
  const query = searchParams["q"] as string;
  const annotationId = searchParams["aid"] as string;
  const annotationType = searchParams["atype"] as string;
  const queryType = searchParams["type"] as string;
  const page = searchParams["page"] as string;
  const minSimilarity = searchParams["minSimilarity"] as string;
  const semanticSearch = searchParams["semantic"] as string;

  const safePage = isNaN(Number.parseInt(page)) ? 0 : Number.parseInt(page);
  let safeQueryType: Lang3sQueryType = "document";
  for (const qt of QueryTypes) {
    if (qt === queryType) {
      safeQueryType = qt;
      break;
    }
  }
  const safeMinSimilarity = isNaN(Number.parseFloat(minSimilarity))
    ? safeQueryType === "document"
      ? 1.0
      : 0.6
    : Number.parseFloat(minSimilarity);

  const safeSemanticSearch = semanticSearch
    ? semanticSearch.toLowerCase() === "true"
    : false;

  return {
    q: query,
    atype: annotationType ?? "entity",
    aid: annotationId,
    stype: safeQueryType,
    page: safePage,
    minSimilarity: safeMinSimilarity,
    semantic: safeSemanticSearch,
  };
};
