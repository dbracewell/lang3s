import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { ChartSchema, SeriesType } from "@/features/reports/schema";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { Chart } from "@/features/reports/types";
import { getMetadata } from "@/features/common/server/queries";
import { MetadataConfiguration } from "@/features/metadata/types";
import { DataType } from "@/lib/db/schema";
import { DataTypeNameToCategoryMap } from "@/features/common/types";
import {
  ChartResult,
  getChartData,
} from "@/features/reports/server/chartingApi";

const LIMIT = 25;

const getEffectiveDataType = (
  axis: SeriesType,
  metadata: MetadataConfiguration,
): DataType => {
  switch (axis.type) {
    case "ANNOTATION_METADATA":
      return metadata["annotation"][axis.value].dataType;
    case "DOCUMENT_METADATA":
      return metadata["document"][axis.value].dataType;
    case "SENTENCE_METADATA":
      return metadata["sentence"][axis.value].dataType;
  }
  return "string";
};

const getEffectiveFormatter = (
  metadata: MetadataConfiguration,
  axis?: SeriesType,
): string | undefined => {
  if (axis == null) {
    return undefined;
  }
  switch (axis.type) {
    case "ANNOTATION_METADATA":
      return metadata["annotation"][axis.value].formatter;
    case "DOCUMENT_METADATA":
      return metadata["document"][axis.value].formatter;
    case "SENTENCE_METADATA":
      return metadata["sentence"][axis.value].formatter;
  }
  return undefined;
};

export const reportsRouter = createTRPCRouter({
  getData: protectedProcedure.input(ChartSchema).query(async ({ input }) => {
    const { x, y, count: countType } = input;

    const metadata = await logAndRethrow(() => getMetadata());
    const x_data_type = getEffectiveDataType(x, metadata);
    const y_data_type = y ? getEffectiveDataType(y, metadata) : undefined;
    const x_formatter = getEffectiveFormatter(metadata, x);
    const y_formatter = getEffectiveFormatter(metadata, y);
    const chartType = Chart.getChartType(
      DataTypeNameToCategoryMap[x_data_type],
      y_data_type ? DataTypeNameToCategoryMap[y_data_type] : undefined,
    );
    const chartData = await getChartData({
      chart_type: chartType,
      x: {
        page: 1,
        page_size: LIMIT,
        type: input.x.type,
        value: input.x.value,
        data_type: x_data_type,
        formatter: x_formatter,
      },
      y: y
        ? {
            page: 1,
            page_size: LIMIT,
            type: y.type,
            value: y.value,
            data_type: y_data_type!,
            formatter: y_formatter,
          }
        : undefined,
      count_type: countType,
    });
    return { ...chartData, chart_type: chartType } as ChartResult;
  }),
});
