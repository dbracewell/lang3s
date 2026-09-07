"use client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ChevronRightIcon, PlusIcon } from "lucide-react";
import { Form } from "@/components/ui/form";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import z from "zod";
import { InputFormField } from "@/components/form-controls/input-form-field";
import { TextareaFormField } from "@/components/form-controls/textarea-form-field";
import { OntologyConceptSchema } from "@/features/ontology/schemas";
import { useDebounce } from "@/hooks/useDebounce";
import { toast } from "sonner";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  addOntologyEntryMutation,
  ontologyNameExistsOptions,
} from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";

export const AddConceptDialog = ({
  parentId,
  parentPath,
  triggerClassName,
}: {
  parentId: number;
  parentPath: string;
  triggerClassName?: string;
}) => {
  const [open, setOpen] = useState(false);
  const form = useForm({
    resolver: zodResolver(OntologyConceptSchema),
    defaultValues: {
      name: "",
      description: "",
      parentId,
    },
  });
  const addConcept = useMutation({
    ...addOntologyEntryMutation({
      client: coreClient,
    }),
    onSuccess: () => toast.success(`Successfully created new concept`),
    onError: () => toast.error("Failed to create new concept"),
  });

  const name = useWatch({ control: form.control, name: "name" });
  const debouncedName = useDebounce(name, 500);
  const { data, refetch } = useQuery({
    ...ontologyNameExistsOptions({
      client: coreClient,
      path: {
        name: debouncedName,
      },
    }),
    enabled: false,
  });

  useEffect(() => {
    if (data != null && data) {
      form.setError(
        "name",
        {
          message: "Name already exists",
          type: "user",
        },
        { shouldFocus: true },
      );
    } else {
      form.clearErrors("name");
    }
  }, [data, form]);

  useEffect(() => {
    form.setValue("parentId", parentId);
  }, [parentId, form]);

  const onClose = (value: boolean) => {
    if (value) {
      setOpen(value);
      return;
    }
    form.reset();
    setOpen(false);
  };

  const onSubmit = (values: z.infer<typeof OntologyConceptSchema>) => {
    addConcept.mutate({
      body: {
        parent_id: values.parentId,
        description: values.description,
        name: values.name,
      },
    });
    onClose(false);
  };
  const pathCrumbs = parentPath.split(".");
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger className={triggerClassName}>
        <PlusIcon />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create concept</DialogTitle>
          <DialogDescription className="sr-only">
            Create a new ontology concept.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="text-muted-foreground flex items-center text-sm">
              <span className="mr-2 font-medium">Parent: </span>
              {pathCrumbs.map((c, i) => (
                <div
                  key={i}
                  className="last:text-dodger-blue-500 flex items-center"
                >
                  {c}
                  {i + 1 < pathCrumbs.length && (
                    <ChevronRightIcon className="mx-1 size-3" />
                  )}
                </div>
              ))}
            </div>
            <InputFormField
              reactHookForm={form}
              onBlur={() => refetch()}
              required
              name={"name"}
              label="Concept Name"
            />
            <TextareaFormField
              reactHookForm={form}
              className={"h-[150px] resize-none"}
              name={"description"}
              label="Concept Description"
            />
            <Button className="w-full">Create</Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
