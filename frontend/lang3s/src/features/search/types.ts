export type Highlight = {
  rank: number;
  text: string;
  a0?: string[];
  a1?: string[];
  time?: string;
  location?: string;
};

export type SearchResult = {
  documentTitle: string;
  documentId: string;
  highlights: Highlight[];
  rank: number;
};

export type SearchResults = {
  type: "annotation" | "document" | "sentence";
  total: number;
  results: SearchResult[];
  entities: { entity: string; count: number }[];
  nextCursor: number | undefined;
};
