import { DataTypeCategory } from "@/features/common/types";
import { capitalize } from "@/lib/utils/formatters";
import { SelectOptionItem } from "@/components/form-controls/select-form-field";
import { Column, sql, SQL } from "drizzle-orm";
import { SeriesType } from "@/features/reports/schema";
import Aliased = SQL.Aliased;

const SERIES_SOURCES = [
  "TOPIC",
  "ANNOTATION",
  "DOCUMENT_METADATA",
  "SENTENCE_METADATA",
  "ANNOTATION_METADATA",
] as const;
const COUNT_TYPES = ["document", "sentence", "mention"] as const;

const CHART_TYPES = [
  "heatmap",
  "barchart",
  "linechart",
  "scatterplot",
] as const;

const SourceToCountType: Record<
  SeriesSourceType,
  Record<SeriesSourceType | "NONE", CountType[]>
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

const DataTypeToChart: Record<
  DataTypeCategory,
  Record<DataTypeCategory | "none", ChartType>
> = {
  string: {
    none: "barchart",
    string: "heatmap",
    number: "linechart",
    date: "linechart",
    boolean: "heatmap",
  },
  boolean: {
    none: "barchart",
    string: "heatmap",
    number: "linechart",
    date: "linechart",
    boolean: "heatmap",
  },
  number: {
    none: "linechart",
    string: "linechart",
    boolean: "linechart",
    number: "scatterplot",
    date: "scatterplot",
  },
  date: {
    none: "linechart",
    string: "linechart",
    boolean: "linechart",
    number: "scatterplot",
    date: "scatterplot",
  },
};

export type CountType = (typeof COUNT_TYPES)[number];
export type SeriesSourceType = (typeof SERIES_SOURCES)[number];
export type ChartType = (typeof CHART_TYPES)[number];
export type DisplayType = "text" | "value" | "text-value";
export type ChartSeries = {
  text1: string | number;
  text2: string | number;
  value1: string | number;
  value2: string | number;
  mentionCount: number;
  sentenceCount: number;
  documentCount: number;
};
export type ChartData = ChartSeries[];

export const Chart = {
  sourceTypes: SERIES_SOURCES,
  countTypes: COUNT_TYPES,
  chartTypes: CHART_TYPES,
  sourceSelectOptions: SERIES_SOURCES.map(
    (source) =>
      ({
        type: "item",
        value: source,
        node: capitalize(source.split("_").join(" "), true),
      }) as SelectOptionItem,
  ),
  getCountTypes: function (x: SeriesSourceType, y?: SeriesSourceType) {
    return SourceToCountType[x][y ?? "NONE"];
  },
  getCountSelectOptions: function (x: SeriesSourceType, y?: SeriesSourceType) {
    return SourceToCountType[x][y ?? "NONE"].map(
      (v) =>
        ({
          type: "item",
          value: v,
          node: capitalize(v, true),
        }) as SelectOptionItem,
    );
  },
  getMetadataType: function (value: SeriesSourceType) {
    switch (value) {
      case "TOPIC":
        return "sentence";
      case "ANNOTATION":
        return "annotation";
      case "DOCUMENT_METADATA":
        return "document";
      case "SENTENCE_METADATA":
        return "sentence";
      case "ANNOTATION_METADATA":
        return "annotation";
    }
  },
  getChartType: function (x: DataTypeCategory, y?: DataTypeCategory) {
    return DataTypeToChart[x][y ?? "none"];
  },
  getCountColumn: function (
    countType: CountType,
    t: {
      documentCount: SQL<number>;
      sentenceCount: SQL<number>;
      mentionCount: SQL<number>;
    },
  ) {
    switch (countType) {
      case "document":
        return t.documentCount;
      case "sentence":
        return t.sentenceCount;
      default:
        return t.mentionCount;
    }
  },
  convertToDisplay: function ({
    content,
    value,
    displayType,
    isValue,
  }: {
    content: Column | Aliased<string>;
    value: Column | Aliased<string> | SQL<string>;
    displayType: DisplayType;
    isValue: boolean;
  }) {
    switch (displayType) {
      case "text":
        return isValue ? sql<string>`${value}` : sql<string>`${content}`;
      case "value":
        return sql<string>`${value}`;
      default:
        return sql<string>`CONCAT(${content}, ' (', ${value}, ')')`;
    }
  },
  getCount: function (series: ChartSeries, countType: CountType) {
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
  },
  getAxisLabel: function (axis: SeriesType) {
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
