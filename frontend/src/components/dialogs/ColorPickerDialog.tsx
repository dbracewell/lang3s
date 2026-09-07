import { AnnotationColors } from "@/lib/constants";
import z from "zod";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import React, { useEffect, useState } from "react";
import { Form } from "@/components/ui/form";
import { cn } from "@/lib/utils/cn";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { PaletteIcon } from "lucide-react";

const colors = Object.keys(AnnotationColors);
const schema = z.object({
  color: z.enum(colors),
});

export const ColorPickerDialog = ({
  defaultColor,
  onSelect,
  title,
}: {
  title?: string | React.ReactNode;
  defaultColor?: string;
  onSelect: (color: string) => void;
}) => {
  const [open, setOpen] = useState(false);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      color: defaultColor ?? colors[0],
    },
  });

  useEffect(() => {
    form.reset({
      color: defaultColor ?? colors[0],
    });
  }, [defaultColor, form]);

  const onSubmit = (values: z.infer<typeof schema>) => {
    onSelect(values.color);
    setOpen(false);
  };

  const currentColor = useWatch({ control: form.control, name: "color" });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "icon-xs" })}
      >
        <PaletteIcon />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title ?? "Color Picker"}</DialogTitle>
          <DialogDescription className="sr-only">
            Select the color to use.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-4 gap-2">
              {colors.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => form.setValue("color", color)}
                  className={cn(
                    "flex items-center gap-2 rounded border p-2 text-sm",
                    currentColor === color && "bg-accent",
                  )}
                >
                  <div
                    className={cn(
                      "aspect-square size-4 shrink-0 border",
                      AnnotationColors[color],
                    )}
                  />
                  {color}
                </button>
              ))}
            </div>
            <Button className="w-full">Select</Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
