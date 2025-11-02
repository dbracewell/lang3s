import { ReadonlyURLSearchParams } from "next/navigation";





export const toSearchParams = (searchParams: ParsedSearchParams) => {
  const params = new URLSearchParams();
  if (!!searchParams.query?.trim()) {
    params.set("q", searchParams.query.trim());
  }
  if (!!searchParams.annotationId?.trim()) {
    params.set("aid", searchParams.annotationId.trim());
  }
  if (
    searchParams.queryType === "annotation" &&
    !!searchParams.annotationType?.trim()
  ) {
    params.set("atype", searchParams.annotationType.trim());
  }
  if (searchParams.semanticSearch && !!searchParams.minSimilarity) {
    params.set("minSimilarity", String(searchParams.minSimilarity));
  }
  if (searchParams.semanticSearch) {
    params.set("semantic", String(true));
  }
  params.set("type", searchParams.queryType);
  if (searchParams.page > 0) {
    params.set("page", String(searchParams.page));
  }
  if (searchParams.lang) {
    params.set("lang", searchParams.lang);
  }
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
  const lang = searchParams["lang"] as string;

  const safePage = isNaN(Number.parseInt(page)) ? 0 : Number.parseInt(page);
  let safeQueryType: QueryType = "document";
  for (const qt of Object.values(QueryTypes)) {
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
    query,
    annotationType: annotationType ?? "entity",
    annotationId,
    queryType: safeQueryType,
    page: safePage,
    minSimilarity: safeMinSimilarity,
    semanticSearch: safeSemanticSearch,
    lang,
  };
};
