export type Highlight = {
  similarity: number;
  text: string;
};

export type SearchResult = {
  documentTitle: string;
  documentId: string;
  highlights: Highlight[];
  rank: number;
};

export type SearchResults = {
  type: "text" | "vector";
  total: number;
  results: SearchResult[];
  nextCursor: number | undefined;
};
