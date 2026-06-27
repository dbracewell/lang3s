import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";
import z from "zod";
import {
  OntologyProperties,
  OntologyPropertyValueDataTypes,
  OntologyPropertyValueSchema,
} from "@/lib/db/schemas/ontology";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Form } from "@/components/ui/form";
import { InputFormField } from "@/components/form-controls/input-form-field";
import { CheckboxFormField } from "@/components/form-controls/checkbox-form-field";
import { capitalize } from "@/lib/utils/formatters";
import {
  SelectFormField,
  SelectOptionItem,
} from "@/components/form-controls/select-form-field";

const formSchema = z.object({
  entries: z.array(
    z.object({
      name: z.string().min(1, "Property name is required."),
      value: OntologyPropertyValueSchema,
    }),
  ),
});

const DataTypeOptions = OntologyPropertyValueDataTypes.map(
  (d) =>
    ({
      type: "item",
      value: d,
      node: <>{capitalize(d)}</>,
    }) as SelectOptionItem,
);

export const AddPropertyDialog = ({
  defaultValues,
  title,
  onSelect,
}: {
  title: string | React.ReactNode;
  defaultValues?: OntologyProperties;
  onSelect: (value: Record<string, any>) => void;
}) => {
  const [open, setOpen] = useState(false);

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      entries: defaultValues
        ? Object.entries(defaultValues).map(([k, v]) => ({
            name: k,
            value: { ...v, definedBy: v.definedBy ?? "" },
          }))
        : [],
    },
  });
  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "entries",
  });

  useEffect(() => {
    form.reset({
      entries: defaultValues
        ? Object.entries(defaultValues).map(([k, v]) => ({
            name: k,
            value: { ...v, definedBy: v.definedBy ?? "" },
          }))
        : [],
    });
  }, [defaultValues, form]);

  const onClose = (value: boolean) => {
    if (value) {
      setOpen(value);
      return;
    }
    form.reset();
    setOpen(false);
  };

  const onSubmit = (v: z.infer<typeof formSchema>) => {
    onSelect(Object.fromEntries(v.entries.map((e) => [e.name, e.value])));
    onClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "icon-xs" })}
      >
        <PencilIcon />
      </DialogTrigger>
      <DialogContent className="flex h-[95%] flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Create, edit, and delete {title} options.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex min-h-0 flex-1 flex-col gap-2"
          >
            <div className="scrollable flex h-full min-h-0 flex-col justify-between">
              <div className="flex flex-1 flex-col gap-2 py-2">
                {fields.map((field, index) => (
                  <div
                    key={field.id}
                    className="bg-card flex h-fit flex-col gap-2 rounded-lg border p-2"
                  >
                    <div className="flex w-full items-start gap-3">
                      <div className="w-full flex-1">
                        <InputFormField
                          reactHookForm={form}
                          placeholder="Property Name"
                          name={`entries.${index}.name`}
                        />
                      </div>
                      <div className="flex justify-end">
                        <Button
                          variant="destructiveOutline"
                          size="icon-xs"
                          type="button"
                          onClick={() => remove(index)}
                        >
                          <Trash2Icon />
                        </Button>
                      </div>
                    </div>
                    <div className="grid w-full grid-cols-2 items-start gap-2">
                      <InputFormField
                        label="Value"
                        reactHookForm={form}
                        name={`entries.${index}.value.value`}
                      />
                      <SelectFormField
                        label="Data Type"
                        defaultValue="Data Type"
                        reactHookForm={form}
                        name={`entries.${index}.value.dataType`}
                        options={DataTypeOptions}
                      />
                      <CheckboxFormField
                        label="Inherit"
                        reactHookForm={form}
                        name={`entries.${index}.value.inherit`}
                      />
                      <CheckboxFormField
                        label="Display"
                        reactHookForm={form}
                        name={`entries.${index}.value.display`}
                      />
                    </div>
                    <div className="flex w-full justify-end">
                      <Button
                        variant="destructiveOutline"
                        size="icon-xs"
                        type="button"
                        onClick={() => remove(index)}
                      >
                        <Trash2Icon />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              className=""
              onClick={() =>
                append({
                  name: "",
                  value: {
                    value: "",
                    dataType: "string",
                    inherit: true,
                    display: false,
                    definedBy: "",
                  },
                })
              }
            >
              <PlusIcon /> Add Row
            </Button>
            <Button className="w-full">Save</Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
