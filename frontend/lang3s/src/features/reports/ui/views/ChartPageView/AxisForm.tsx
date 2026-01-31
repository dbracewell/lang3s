import { FieldValues, Path, useForm, UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ChartSchema, ChartSchemaType } from "@/features/reports/schema";
import { Form } from "@/components/ui/form";
import { cn } from "@/lib/utils/cn";
import {
  SelectFormField,
  SelectOptionItem,
} from "@/components/form-controls/select-form-field";
import { Button } from "@/components/ui/button";
import { MinusIcon, PlusIcon } from "lucide-react";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { useMemo, useState } from "react";
import { DataTypeNameToCategoryMap } from "@/features/common/types";
import { Chart, SeriesSourceType } from "@/features/reports/types";
import {
  DefaultOntologyTrigger,
  OntologySelectorDialog,
} from "@/features/ontology/ui/components/OntologySelectorDialog";
import { MetadataConfiguration, MetadataItem } from "@/features/metadata/types";
import { DataType } from "@/lib/db/schemas/metadata";

type DualAxisFormProps = {
  defaultValues?: ChartSchemaType;
  setAxis: (axis: ChartSchemaType) => void;
};

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

export const DualAxisForm = ({ defaultValues, setAxis }: DualAxisFormProps) => {
  const { data: metadata } = useTRPCQuery((trpc) =>
    trpc.system.getMetadata.queryOptions(),
  );
  const form = useForm({
    resolver: zodResolver(ChartSchema),
    defaultValues: {
      x: defaultValues?.x ?? {
        type: "ANNOTATION",
        value: "ENTITY",
        dataType: "string",
        display: "value",
      },
      y: defaultValues?.y,
      count: "mention",
    },
  });

  const x = form.watch("x");
  const y = form.watch("y");

  const countTypeOptions = useMemo(() => {
    return Chart.getCountSelectOptions(x.type, y?.type);
  }, [x.type, y?.type]);

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(setAxis)}
        className="bg-card mx-auto w-full max-w-xl space-y-4 rounded-lg border p-2"
      >
        <h1>Chart Wizard</h1>
        {JSON.stringify(form.formState.errors)}
        <div
          className={cn("grid grid-cols-1", y != null && "grid-cols-2! gap-4")}
        >
          <div className="space-y-4 rounded-lg border p-2">
            <h3 className="font-bold">Series 1</h3>
            <SeriesInformation
              typeField={"x.type"}
              valueField={"x.value"}
              dataTypeField={"x.dataType"}
              displayField={"x.display"}
              form={form}
              axisType={form.watch("x.type")}
              metadata={
                metadata ?? { document: {}, annotation: {}, sentence: {} }
              }
            />
          </div>
          {y != null && (
            <div className="space-y-4 rounded-lg border p-2">
              <h3 className="font-bold">Series 2</h3>
              <SeriesInformation
                typeField={"y.type"}
                valueField={"y.value"}
                dataTypeField={"y.dataType"}
                displayField={"y.display"}
                form={form}
                axisType={form.watch("y.type") ?? "TOPIC"}
                metadata={
                  metadata ?? { document: {}, annotation: {}, sentence: {} }
                }
              />
            </div>
          )}
        </div>
        <div className="flex items-center">
          <SelectFormField
            options={countTypeOptions}
            reactHookForm={form}
            name="count"
            label="Count By"
            selectTriggerClassName="w-[200px]"
          />
        </div>
        <div className={cn("flex items-center justify-between")}>
          {y == null ? (
            <Button
              type="button"
              size="sm"
              onClick={async () => {
                form.setValue("count", Chart.getCountTypes(x.type)[0]);
                form.setValue("y.type", "ANNOTATION");
                form.setValue("y.dataType", "string");
                form.setValue("y.value", "ENTITY");
                form.setValue("y.display", "value");
              }}
            >
              <PlusIcon /> Series
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={() => {
                form.setValue("y", undefined);
              }}
            >
              <MinusIcon /> Series
            </Button>
          )}
          <Button>Submit</Button>
        </div>
      </form>
    </Form>
  );
};

const SeriesInformation = <T extends FieldValues>({
  typeField,
  valueField,
  dataTypeField,
  displayField,
  form,
  metadata,
  axisType,
}: {
  typeField: Path<T>;
  valueField: Path<T>;
  dataTypeField: Path<T>;
  displayField: Path<T>;
  form: UseFormReturn<T>;
  metadata: MetadataConfiguration;
  axisType: SeriesSourceType;
}) => {
  const metadataOptions = useMemo(
    () => getMetadataOptions(metadata, axisType),
    [metadata, axisType],
  );
  const [selected, setSelected] = useState<string[]>([]);

  const DisplayOptions = useMemo(() => {
    switch (axisType) {
      case "TOPIC":
        return [
          {
            type: "item",
            value: "text",
            node: <>Topic Name</>,
          } satisfies SelectOptionItem,
        ];
      case "ANNOTATION":
        return [
          {
            type: "item",
            value: "text",
            node: <>Annotation Text</>,
          } satisfies SelectOptionItem,
          {
            type: "item",
            value: "value",
            node: <>Annotation Value</>,
          } satisfies SelectOptionItem,
          {
            type: "item",
            value: "text-value",
            node: <>Annotation Text-Value</>,
          } satisfies SelectOptionItem,
        ];
      default:
        return [
          {
            type: "item",
            value: "value",
            node: <>Metadata Value</>,
          } satisfies SelectOptionItem,
          {
            type: "item",
            value: "text-value",
            node: <>Metadata Key-Value</>,
          } satisfies SelectOptionItem,
        ];
    }
  }, [axisType]);

  return (
    <div className="flex flex-col gap-4">
      <SelectFormField
        options={Chart.sourceSelectOptions}
        reactHookForm={form}
        name={typeField}
        label="Series Element"
        onValueChange={async (v) => {
          switch (v as SeriesSourceType) {
            case "TOPIC":
              form.setValue(valueField, "TOPIC" as any);
              form.setValue(dataTypeField, "string" as any);
              break;
            case "ANNOTATION":
              form.setValue(valueField, "ENTITY" as any);
              form.setValue(dataTypeField, "string" as any);
              break;
            default:
              form.setValue(valueField, "" as any);
              form.setValue(dataTypeField, "string" as any);
          }
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
          <div>{selected.join(" ")}</div>
        </>
      )}
      {[
        "DOCUMENT_METADATA",
        "SENTENCE_METADATA",
        "ANNOTATION_METADATA",
      ].includes(axisType) && (
        <SelectFormField
          options={metadataOptions}
          onValueChange={(v) => {
            form.setValue(
              dataTypeField,
              DataTypeNameToCategoryMap[
                metadata[Chart.getMetadataType(axisType)][v]
                  .dataType as DataType
              ] as any,
            );
          }}
          reactHookForm={form}
          name={valueField}
          label="Metadata Key"
        />
      )}
      <SelectFormField
        reactHookForm={form}
        defaultValue={"text"}
        name={displayField}
        label="Display Value"
        options={DisplayOptions}
      />
    </div>
  );
};
