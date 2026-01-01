export type DocumentHighlight = {
  rank: number;
  text: string;
  a0?: string[];
  a1?: string[];
  time?: string;
  location?: string;
};

export type DocumentSearchResult = {
  documentTitle: string;
  documentId: string;
  highlights: DocumentHighlight[];
  rank: number;
};

export type AnnotationHighlight = {
  documentTitle: string;
  documentId: string;
  annotationId: string;
  rank: number;
};

export type AnnotationSearchResult = {
  text: string;
  value: string;
  a0: string[] | null;
  a1: string[] | null;
  time: string | null;
  location: string | null;
  highlights: AnnotationHighlight[];
  rank: number;
};

export type TopicHighlight = {
  sentence: string;
  documentId: string;
  sentenceAid: string;
  rank: number;
};

export type TopicSearchResult = {
  name: string;
  id: string;
  highlights: TopicHighlight[];
  rank: number;
};

export type SearchResults<T> = {
  total: number;
  results: T[];
  nextCursor: number | undefined;
};
