"use client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { buttonVariants } from "@/components/ui/button";
import { FolderPlusIcon } from "lucide-react";
import { Form } from "@/components/ui/form";
import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CreateProjectSchema } from "@/features/projects/schemas";
import z from "zod";
import { LoadingButton } from "@/components/ui/loading-button";
import { InputFormField } from "@/components/form-controls/input-form-field";
import { TextareaFormField } from "@/components/form-controls/textarea-form-field";

export const CreateProjectDialog = () => {
  const [open, setOpen] = useState(false);
  const form = useForm<z.infer<typeof CreateProjectSchema>>({
    resolver: zodResolver(CreateProjectSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const onSubmit = (data: z.infer<typeof CreateProjectSchema>) => {
    console.log(data);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "sm" })}
      >
        <FolderPlusIcon /> New Project
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
          <DialogDescription className="sr-only">
            Create a new project
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <InputFormField
              reactHookForm={form}
              name="name"
              label="Project Name"
              required={true}
              placeholder="Project xyz..."
            />
            <TextareaFormField
              reactHookForm={form}
              name="description"
              label="Project Description"
              required={true}
              className="h-[200px] resize-none"
              placeholder="Project xyz investigates...."
            />
            <LoadingButton isLoading={false} className="w-full">
              Create Project
            </LoadingButton>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
