import { CountType, SeriesType } from "@/clients/analytics";

export const SERIES_SOURCES = [
  "TOPIC",
  "ANNOTATION",
  "DOCUMENT_METADATA",
  "SENTENCE_METADATA",
  "ANNOTATION_METADATA",
] as const;

const SourceToCountType: Record<
  SeriesType,
  Record<SeriesType | "NONE", CountType[]>
> = {
  TOPIC: {
    NONE: ["document", "sentence"],
    TOPIC: ["document", "sentence"],
    ANNOTATION: ["document", "sentence"],
    DOCUMENT_METADATA: ["document"],
    SENTENCE_METADATA: ["sentence"],
    ANNOTATION_METADATA: ["mention"],
  },
  ANNOTATION: {
    NONE: ["document", "sentence", "mention"],
    TOPIC: ["document", "sentence"],
    ANNOTATION: ["document", "sentence"],
    DOCUMENT_METADATA: ["document"],
    SENTENCE_METADATA: ["sentence"],
    ANNOTATION_METADATA: ["mention"],
  },
  DOCUMENT_METADATA: {
    NONE: ["document"],
    TOPIC: ["document"],
    ANNOTATION: ["document"],
    DOCUMENT_METADATA: ["document"],
    SENTENCE_METADATA: ["sentence"],
    ANNOTATION_METADATA: ["mention"],
  },
  SENTENCE_METADATA: {
    NONE: ["sentence"],
    TOPIC: ["sentence"],
    ANNOTATION: ["sentence"],
    DOCUMENT_METADATA: ["document"],
    SENTENCE_METADATA: ["sentence"],
    ANNOTATION_METADATA: ["mention"],
  },
  ANNOTATION_METADATA: {
    NONE: ["mention"],
    TOPIC: ["sentence"],
    ANNOTATION: ["sentence"],
    DOCUMENT_METADATA: ["document"],
    SENTENCE_METADATA: ["sentence"],
    ANNOTATION_METADATA: ["mention"],
  },
};
