import { ChartData, CountType, SeriesType } from "@/clients/analytics";
import { capitalize } from "@/lib/utils/formatters";
import { SelectOptionItem } from "@/components/form-controls/select-form-field";

export const selectCountValue = (series: ChartData, countType: CountType) => {
  switch (countType) {
    case "mention":
      return series.mentionCount;
    case "sentence":
      return series.sentenceCount;
    case "document":
      return series.documentCount;
  }
};

export const selectCountDataKey = (countType: CountType) => {
  switch (countType) {
    case "mention":
      return "mentionCount";
    case "sentence":
      return "sentenceCount";
    case "document":
      return "documentCount";
  }
};

const allowableCountTypes: Record<SeriesType, Set<CountType>> = {
  TOPIC: new Set(["document", "sentence"]),
  ANNOTATION: new Set(["document", "sentence", "mention"]),
  ANNOTATION_METADATA: new Set(["document", "sentence", "mention"]),
  DOCUMENT_METADATA: new Set(["document"]),
  SENTENCE_METADATA: new Set(["document", "sentence"]),
};

export const selectAllowableCountTypes = (x: SeriesType, y?: SeriesType) => {
  if (y == null) {
    return [...allowableCountTypes[x]];
  }
  return [...allowableCountTypes[x].intersection(allowableCountTypes[y])];
};

export const createSelectableCountTypes = (x: SeriesType, y?: SeriesType) => {
  return selectAllowableCountTypes(x, y).map(
    (v) =>
      ({
        type: "item",
        value: v,
        node: capitalize(v, true),
      }) as SelectOptionItem,
  );
};

export const SeriesSelectOptions = [
  {
    type: "item",
    value: "TOPIC",
    node: "Topic",
  },
  {
    type: "item",
    value: "ANNOTATION",
    node: "Annotation",
  },
  {
    type: "item",
    value: "DOCUMENT_METADATA",
    node: "Document Metadata",
  },
  {
    type: "item",
    value: "SENTENCE_METADATA",
    node: "Sentence Metadata",
  },
  {
    type: "item",
    value: "ANNOTATION_METADATA",
    node: "Annotation Metadata",
  },
] as SelectOptionItem[];

export const truncateLabel = (label: string, length: number) => {
  if (label.length <= length) {
    return label;
  }
  return label.substring(0, length) + "...";
};
