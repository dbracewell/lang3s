"use client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  parseAsString,
  parseAsStringEnum,
  useQueryState,
  useQueryStates,
} from "nuqs";
import { parseAsBoolean } from "nuqs/server";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { MetadataSchema, MetadataSchemaType } from "@/features/common/schemas";
import { Form } from "@/components/ui/form";
import { InputFormField } from "@/components/form-controls/input-form-field";
import {
  SelectFormField,
  SelectOptionItem,
} from "@/components/form-controls/select-form-field";
import { capitalize } from "@/lib/utils/formatters";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { useRouter } from "next/navigation";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { cn } from "@/lib/utils/cn";
import { useEffect, useMemo } from "react";
import { LoadingButton } from "@/components/ui/loading-button";
import { DataTypeNames } from "@/features/common/types";
import { MetadataSources } from "@/features/metadata/types";

const SourceOptions = MetadataSources.map(
  (source) =>
    ({
      type: "item",
      value: source,
      node: <>{capitalize(source)}</>,
    }) as SelectOptionItem,
);

const DataTypeOptions = DataTypeNames.map(
  (source) =>
    ({
      type: "item",
      value: source,
      node: <>{capitalize(source)}</>,
    }) as SelectOptionItem,
);

export const MetadataDialog = ({
  possibleMetadata,
}: {
  possibleMetadata: { source: string; key: string }[];
}) => {
  const router = useRouter();
  const [open, setOpen] = useQueryState(
    "edit",
    parseAsBoolean.withDefault(false).withOptions({ clearOnDefault: true }),
  );

  const [metadataValues, setMetadataValues] = useQueryStates({
    id: parseAsString.withOptions({ clearOnDefault: true }),
    name: parseAsString.withOptions({ clearOnDefault: true }),
    dataType: parseAsStringEnum([...DataTypeNames]).withOptions({
      clearOnDefault: true,
    }),
    source: parseAsStringEnum([...MetadataSources]).withOptions({
      clearOnDefault: true,
    }),
    formatter: parseAsString,
  });

  const form = useForm<MetadataSchemaType>({
    resolver: zodResolver(MetadataSchema),
    defaultValues: {
      name: metadataValues.name ?? "",
      dataType: metadataValues.dataType ?? "string",
      source: metadataValues.source ?? "document",
      formatter: metadataValues.formatter ?? "YYYY-MM-dd",
    },
  });

  useEffect(() => {
    form.reset({
      name: metadataValues.name ?? "",
      dataType: metadataValues.dataType ?? "string",
      source: metadataValues.source ?? "document",
      formatter: metadataValues.formatter ?? "YYYY-MM-dd",
    });
  }, [metadataValues, form]);

  const onClose = async () => {
    form.reset();
    await setOpen(false);
    await setMetadataValues({});
  };

  const createMutation = useTRPCMutation((trpc) => ({
    mutation: trpc.system.createMetadata.mutationOptions({
      onSuccess: () => {
        onClose();
        router.refresh();
      },
    }),
    successToast: "Metadata created successfully",
    errorToast: "Error creating metadata",
  }));

  const updateMutation = useTRPCMutation((trpc) => ({
    mutation: trpc.system.updateMetadata.mutationOptions({
      onSuccess: () => {
        onClose();
        router.refresh();
      },
    }),
    successToast: "Metadata updated successfully",
    errorToast: "Error updating metadata",
  }));

  const onSubmit = (values: MetadataSchemaType) => {
    if (isEdit) {
      updateMutation.mutate({
        id: metadataValues.id!,
        values,
      });
    } else {
      createMutation.mutate(values);
    }
  };
  const dataType = form.watch("dataType");
  const source = form.watch("source");
  const isEdit = metadataValues.id ?? false;

  const nameOptions = useMemo(() => {
    if (isEdit && metadataValues.name) {
      return [
        {
          type: "item",
          value: metadataValues.name,
        } as SelectOptionItem,
      ];
    }
    return possibleMetadata
      .filter((s) => s.source === source)
      .map(
        (s) =>
          ({
            type: "item",
            value: s.key,
          }) as SelectOptionItem,
      );
  }, [source, possibleMetadata, metadataValues.name]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        className={cn(
          "",
          (dataType === "date" || dataType === "datetime") &&
            "lg:max-w-[770px]!",
        )}
      >
        <DialogHeader>
          <DialogTitle>Metadata Editor</DialogTitle>
          <DialogDescription>Something</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className={cn(
              "grid h-fit gap-6",
              dataType === "date" || dataType === "datetime"
                ? "grid-cols-2"
                : "grid-cols-1",
            )}
          >
            <div className="flex h-full flex-col gap-4">
              <SelectFormField
                reactHookForm={form}
                required
                name={"name"}
                label={"Metadata name"}
                options={nameOptions}
              />
              <SelectFormField
                reactHookForm={form}
                name="source"
                label="Source"
                required
                options={
                  isEdit && metadataValues.source
                    ? [
                        {
                          type: "item",
                          value: metadataValues.source,
                        } as SelectOptionItem,
                      ]
                    : SourceOptions
                }
              />
              <SelectFormField
                reactHookForm={form}
                onValueChange={(v) => {
                  if (v === "date" || v === "datetime") {
                    form.setValue("formatter", "yyyy-MM-dd");
                  }
                  if (v === "float") {
                    form.setValue("formatter", "2");
                  }
                }}
                name="dataType"
                label="Data Type"
                required
                description="How this metadata value should be represented"
                options={DataTypeOptions}
              />
              {(dataType === "date" || dataType === "datetime") && (
                <InputFormField
                  reactHookForm={form}
                  type="text"
                  emptyToNull={true}
                  name="formatter"
                  label="Date Formatter"
                  description="Format of the date/datetime field."
                />
              )}
              {dataType === "float" && (
                <InputFormField
                  reactHookForm={form}
                  type="number"
                  emptyToNull={true}
                  name="formatter"
                  label="Decimal Places"
                  description="How many decimal places to use."
                />
              )}
              <LoadingButton isLoading={createMutation.isPending}>
                {isEdit ? "Save Changes" : "Create"}
              </LoadingButton>
            </div>
            {(dataType === "date" || dataType === "datetime") && (
              <ScrollableBox.Container className="h-[430px] lg:h-fit lg:w-[350px]">
                <ScrollableBox.ScrollArea outerClassName="p-0! text-xs font-mono">
                  <table>
                    <thead>
                      <tr className="bg-heading sticky top-0 text-white">
                        <td className="p-0.5">Token</td>
                        <td className="p-0.5">Description</td>
                        <td className="p-0.5">Example</td>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="p-0.5">yyyy</td>
                        <td className="p-0.5">Year</td>
                        <td className="p-0.5">2025</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">yy</td>
                        <td className="p-0.5">Last two digits of year</td>
                        <td className="p-0.5">25</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">MM</td>
                        <td className="p-0.5">Month number (01-12)</td>
                        <td className="p-0.5">12</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">MMM</td>
                        <td className="p-0.5">Short month name</td>
                        <td className="p-0.5">Dec</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">MMMM</td>
                        <td className="p-0.5">Full month name</td>
                        <td className="p-0.5">December</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">dd</td>
                        <td className="p-0.5">Day of the month (01-31)</td>
                        <td className="p-0.5">23</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">do</td>
                        <td className="p-0.5">Day of the month with ordinal</td>
                        <td className="p-0.5">23rd</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">eee</td>
                        <td className="p-0.5">Short day of the week</td>
                        <td className="p-0.5">Tue</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">eeee</td>
                        <td className="p-0.5">Full day of the week</td>
                        <td className="p-0.5">Tuesday</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">HH</td>
                        <td className="p-0.5">
                          Hours in 24-hour format (00-23)
                        </td>
                        <td className="p-0.5">14</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">hh</td>
                        <td className="p-0.5">
                          Hours in 12-hour format (01-12)
                        </td>
                        <td className="p-0.5">02</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">mm</td>
                        <td className="p-0.5">Minutes (00-59)</td>
                        <td className="p-0.5">29</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">ss</td>
                        <td className="p-0.5">Seconds (00-59)</td>
                        <td className="p-0.5">00</td>
                      </tr>
                      <tr>
                        <td className="p-0.5">a</td>
                        <td className="p-0.5">AM/PM</td>
                        <td className="p-0.5">PM</td>
                      </tr>
                    </tbody>
                  </table>
                </ScrollableBox.ScrollArea>
              </ScrollableBox.Container>
            )}
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
