import { capitalize } from "@/lib/utils/formatters";
import { SelectOptionItem } from "@/components/form-controls/select-form-field";
import { SeriesFormType } from "@/features/reports/schema";
import {
  ChartData,
  ChartType,
  CountType,
  SeriesType,
} from "@/clients/analytics";

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

export const getChartTypeTitle = (chartType: ChartType) => {
  switch (chartType) {
    case "barchart":
      return "Bar Chart";
    case "linechart":
      return "Line Chart";
    case "heatmap":
      return "Heatmap";
    default:
      return "Scatterplot";
  }
};

export const Chart = {
  sourceSelectOptions: SERIES_SOURCES.map(
    (source) =>
      ({
        type: "item",
        value: source,
        node: capitalize(source.split("_").join(" "), true),
      }) as SelectOptionItem,
  ),
  getCountTypes: function (x: SeriesType, y?: SeriesType) {
    return SourceToCountType[x][y ?? "NONE"];
  },
  getCountSelectOptions: function (x: SeriesType, y?: SeriesType) {
    return SourceToCountType[x][y ?? "NONE"].map(
      (v) =>
        ({
          type: "item",
          value: v,
          node: capitalize(v, true),
        }) as SelectOptionItem,
    );
  },
  getMetadataType: function (value: SeriesType) {
    switch (value) {
      case "TOPIC":
        return "sentences";
      case "ANNOTATION":
        return "annotations";
      case "DOCUMENT_METADATA":
        return "documents";
      case "SENTENCE_METADATA":
        return "sentences";
      case "ANNOTATION_METADATA":
        return "annotations";
    }
  },
  getCount: function (series: ChartData, countType: CountType) {
    switch (countType) {
      case "mention":
        return series.mentionCount;
      case "sentence":
        return series.sentenceCount;
      case "document":
        return series.documentCount;
    }
  },
  formatCountTypeName: function (countType: CountType) {
    switch (countType) {
      case "mention":
        return "Mentions";
      case "sentence":
        return "Sentences";
      case "document":
        return "Documents";
    }
    return "Mentions";
  },
  getAxisLabel: function (axis: SeriesFormType) {
    switch (axis.type) {
      case "TOPIC":
        return "Topics";
      default:
        return capitalize(axis.value.split("_").join(" "), true);
    }
  },
  getCountDataKey: function (countType: CountType) {
    switch (countType) {
      case "mention":
        return "mentionCount";
      case "sentence":
        return "sentenceCount";
      case "document":
        return "documentCount";
    }
  },
};
