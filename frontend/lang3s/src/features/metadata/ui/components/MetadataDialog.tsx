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
import { DataTypeNames, MetadataSources } from "@/lib/db/schemas/metadata";

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
      <DialogContent className={cn("", dataType === "date" && "max-w-215!")}>
        <DialogHeader>
          <DialogTitle>Metadata Editor</DialogTitle>
          <DialogDescription>Something</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className={cn(
              "grid h-fit gap-6",
              dataType === "date" ? "grid-cols-2" : "grid-cols-1",
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
              {dataType === "date" && (
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
            {dataType === "date" && (
              <ScrollableBox.Container className="h-100 lg:w-100">
                <ScrollableBox.ScrollArea outerClassName="p-0! text-xs font-mono">
                  <table>
                    <thead>
                      <tr className="bg-heading font-bold text-white">
                        <td className="p-1">Token</td>
                        <td className="p-1">Description</td>
                        <td className="p-1">Example</td>
                      </tr>
                    </thead>
                    <tbody className="divide-border divide-y">
                      <tr>
                        <td className="p-1 text-center">%Y</td>
                        <td className="p-1">
                          Year with century as a decimal number
                        </td>
                        <td className="p-1">2026</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%y</td>
                        <td className="p-1">Year without century (00-99)</td>
                        <td className="p-1">26</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%m</td>
                        <td className="p-1">
                          Month as a zero-padded decimal number
                        </td>
                        <td className="p-1">02</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%b</td>
                        <td className="p-1">Abbreviated month name</td>
                        <td className="p-1">Feb</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%B</td>
                        <td className="p-1">Full month name</td>
                        <td className="p-1">February</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%d</td>
                        <td className="p-1">
                          Day of the month as a zero-padded decimal
                        </td>
                        <td className="p-1">04</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%a</td>
                        <td className="p-1">Abbreviated weekday name</td>
                        <td className="p-1">Wed</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%A</td>
                        <td className="p-1">Full weekday name</td>
                        <td className="p-1">Wednesday</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%H</td>
                        <td className="p-1">
                          Hour (24-hour clock) as a zero-padded decimal
                        </td>
                        <td className="p-1">11</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%I</td>
                        <td className="p-1">
                          Hour (12-hour clock) as a zero-padded decimal
                        </td>
                        <td className="p-1">11</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%M</td>
                        <td className="p-1">
                          Minute as a zero-padded decimal number
                        </td>
                        <td className="p-1">47</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%S</td>
                        <td className="p-1">
                          Second as a zero-padded decimal number
                        </td>
                        <td className="p-1">20</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%p</td>
                        <td className="p-1">
                          Locale's equivalent of either AM or PM
                        </td>
                        <td className="p-1">AM</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%j</td>
                        <td className="p-1">
                          Day of the year as a zero-padded decimal
                        </td>
                        <td className="p-1">035</td>
                      </tr>
                      <tr>
                        <td className="p-1 text-center">%f</td>
                        <td className="p-1">Microsecond as a decimal number</td>
                        <td className="p-1">000000</td>
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
