import { ChartType, CountType, SeriesType } from "@/clients/analytics";
import { SeriesFormType } from "@/features/reports/schema";
import { capitalize } from "@/lib/utils/formatters";

export const formatChartName = (chartType: ChartType) => {
  switch (chartType) {
    case "barchart":
      return "Bar Chart";
    case "linechart":
      return "Line Chart";
    case "heatmap":
      return "Heatmap";
    default:
      return "Scatter Plot";
  }
};

export const formatMetadataType = (value: SeriesType) => {
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
};

export const formatCountTypeName = (countType: CountType) => {
  switch (countType) {
    case "mention":
      return "Mentions";
    case "sentence":
      return "Sentences";
    case "document":
      return "Documents";
  }
};

export const formatAxisLabel = (axis: SeriesFormType) => {
  switch (axis.type) {
    case "TOPIC":
      return "Topics";
    default:
      return capitalize(axis.value.split("_").join(" "), true);
  }
};
