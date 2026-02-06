"use client";
import { FieldValues, Path, useForm, UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChartFormSchema, ChartFormType } from "@/features/reports/schema";
import { Form } from "@/components/ui/form";
import { cn } from "@/lib/utils/cn";
import {
  SelectFormField,
  SelectOptionItem,
} from "@/components/form-controls/select-form-field";
import { Button } from "@/components/ui/button";
import { MinusIcon, PlusIcon } from "lucide-react";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { useEffect, useMemo, useState } from "react";
import { Chart, SeriesSourceType } from "@/features/reports/types";
import {
  DefaultOntologyTrigger,
  OntologySelectorDialog,
} from "@/features/ontology/ui/components/OntologySelectorDialog";
import { MetadataConfiguration, MetadataItem } from "@/features/metadata/types";
import { useChartParams } from "@/features/reports/hooks/useChartParams";
import { useRouter } from "next/navigation";
import { formatURL } from "@/lib/utils/formatters";

const getMetadataOptions = (
  metadata: MetadataConfiguration,
  source: SeriesSourceType,
) => {
  if (metadata == null) return [];
  const records: Record<string, MetadataItem> =
    metadata[Chart.getMetadataType(source)];
  return Object.entries(records).map(
    ([name, info]) =>
      ({
        type: "item",
        value: name,
        node: (
          <>
            {name} - {info.dataType}
          </>
        ),
      }) as SelectOptionItem,
  );
};

export const DualAxisForm = () => {
  const router = useRouter();
  const [params] = useChartParams();

  const { data: metadata } = useTRPCQuery((trpc) =>
    trpc.system.getMetadata.queryOptions(),
  );

  const form = useForm({
    resolver: zodResolver(ChartFormSchema),
    defaultValues: {
      x: {
        type: params.xType ?? "ANNOTATION",
        value: params.xValue ?? "ALL.Entity",
      },
      y: params.yType
        ? {
            type: params.yType,
            value: params.yValue,
          }
        : undefined,
      count: params.count || "mention",
    },
  });

  const onSubmit = (values: ChartFormType) => {
    router.push(
      formatURL("/reports/charts/view", {
        xPage: params.xPage,
        yPage: params.yPage,
        xType: values.x.type,
        xValue: values.x.value,
        yType: values.y ? values.y.type : "",
        yValue: values.y ? values.y.value : "",
        count: values.count,
      }),
    );
  };

  const x = form.watch("x");
  const y = form.watch("y");
  const countType = form.watch("count");

  const countTypeOptions = useMemo(() => {
    return Chart.getCountSelectOptions(x.type, y?.type);
  }, [x.type, y?.type]);

  useEffect(() => {
    const currentCountType = form.getValues("count");
    if (!!currentCountType) return;
    const possibleTypes = Chart.getCountTypes(x.type, y?.type);
    form.setValue("count", possibleTypes[0]);
  }, [x, y, countTypeOptions, form]);

  const updateCountType = (
    xType: SeriesSourceType,
    yType?: SeriesSourceType,
  ) => {
    const possibleTypes = Chart.getCountTypes(xType, yType);
    if (possibleTypes.length === 1 || !possibleTypes.includes(countType)) {
      form.setValue("count", possibleTypes[0]);
    }
  };

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="bg-card m-auto flex h-full w-full max-w-4xl flex-col space-y-4 rounded-lg border p-5 shadow-sm lg:h-120"
      >
        <h1>Define your Chart series</h1>
        <div className={cn("flex items-center justify-start")}>
          {y == null ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={async () => {
                updateCountType(x.type, "ANNOTATION");
                form.setValue("y.type", "ANNOTATION");
                form.setValue("y.value", "");
              }}
            >
              <PlusIcon /> Add Series
            </Button>
          ) : (
            <Button
              type="button"
              variant="destructiveGhost"
              size="sm"
              className="w-full"
              onClick={() => {
                form.setValue("y", undefined);
              }}
            >
              <MinusIcon /> Remove Series 2
            </Button>
          )}
        </div>
        <div className="flex flex-1 flex-col justify-between gap-4">
          <div
            className={cn(
              "grid grid-cols-1 gap-4",
              y != null && "lg:grid-cols-2!",
            )}
          >
            <div className="bg-alternate-row space-y-4 rounded-lg border p-2">
              <h3 className="font-bold">Series 1</h3>
              <SeriesInformation
                typeField={"x.type"}
                valueField={"x.value"}
                onTypeChange={(newX) => {
                  updateCountType(newX, y?.type);
                }}
                form={form}
                axisType={form.watch("x.type")}
                metadata={
                  metadata ?? { document: {}, annotation: {}, sentence: {} }
                }
              />
            </div>
            {y != null && (
              <div className="bg-alternate-row space-y-4 rounded-lg border p-2">
                <h3 className="flex items-center justify-between font-bold">
                  <span>Series 2</span>
                </h3>
                <SeriesInformation
                  typeField={"y.type"}
                  valueField={"y.value"}
                  onTypeChange={(newY) => {
                    updateCountType(x.type, newY);
                  }}
                  form={form}
                  axisType={form.watch("y.type") ?? "TOPIC"}
                  metadata={
                    metadata ?? { document: {}, annotation: {}, sentence: {} }
                  }
                />
              </div>
            )}
          </div>
          <div className="flex items-end justify-between gap-3">
            <div className="flex items-center">
              <SelectFormField
                options={countTypeOptions}
                reactHookForm={form}
                name="count"
                label="Count By"
                selectTriggerClassName="w-[200px]"
              />
            </div>
            <Button>Create Chart</Button>
          </div>
        </div>
      </form>
    </Form>
  );
};

const SeriesInformation = <T extends FieldValues>({
  typeField,
  valueField,
  form,
  metadata,
  axisType,
  onTypeChange,
}: {
  typeField: Path<T>;
  valueField: Path<T>;
  form: UseFormReturn<T>;
  metadata: MetadataConfiguration;
  axisType: SeriesSourceType;
  onTypeChange: (newType: SeriesSourceType) => void;
}) => {
  const metadataOptions = useMemo(
    () => getMetadataOptions(metadata, axisType),
    [metadata, axisType],
  );
  const [selected, setSelected] = useState<string[]>([]);

  return (
    <div className="flex flex-col gap-4">
      <SelectFormField
        options={Chart.sourceSelectOptions}
        reactHookForm={form}
        name={typeField}
        label="Series Element"
        onValueChange={(v) => {
          form.setValue(valueField, "" as any);
          onTypeChange(v as SeriesSourceType);
        }}
      />
      {axisType === "ANNOTATION" && (
        <>
          <OntologySelectorDialog
            trigger={<DefaultOntologyTrigger />}
            onSelect={(v) => {
              setSelected(v);
              form.setValue(valueField, v.join(",") as any);
            }}
          />
          <div className="scrollable flex h-20 flex-col gap-1 text-sm">
            <h3>Selected Ontology Concepts</h3>
            {selected.length === 0 ? (
              <span className="text-muted-foreground">
                No Ontology Concepts Selected
              </span>
            ) : (
              selected.map((v) => <div key={v}>• {v}</div>)
            )}
          </div>
        </>
      )}
      {[
        "DOCUMENT_METADATA",
        "SENTENCE_METADATA",
        "ANNOTATION_METADATA",
      ].includes(axisType) && (
        <SelectFormField
          options={metadataOptions}
          reactHookForm={form}
          name={valueField}
          label="Metadata Key"
        />
      )}
    </div>
  );
};
