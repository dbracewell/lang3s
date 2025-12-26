import z from "zod";
import React, { useEffect, useRef, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { randomAlphaUnderscore } from "@/lib/utils/random";

const schema = z.object({ values: z.record(z.string(), z.any()) });

export const KeyValueFormDialog = ({
  defaultValues,
  title,
  onSelect,
}: {
  title: string | React.ReactNode;
  defaultValues?: Record<string, string>;
  onSelect: (value: Record<string, any>) => void;
}) => {
  const [open, setOpen] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [values, setValues] = useState<
    { id: string; key: string; value: string }[]
  >(
    Object.entries(defaultValues ?? {}).map(([k, v]) => ({
      id: randomAlphaUnderscore(20),
      key: k,
      value: v,
    })),
  );

  useEffect(() => {
    setValues(
      Object.entries(defaultValues ?? {}).map(([k, v]) => ({
        id: randomAlphaUnderscore(20),
        key: k,
        value: v,
      })),
    );
  }, [defaultValues]);

  const formRef = useRef<HTMLFormElement>(null);

  const onClose = (value: boolean) => {
    if (value) {
      setOpen(value);
      return;
    }
    formRef.current?.reset();
    setValues([]);
    setErrors([]);
    setOpen(false);
  };

  const onSubmit = () => {
    if (formRef.current == null) return;
    const formData = new FormData(formRef.current);
    const fromObject = Object.fromEntries(formData.entries());
    const newValues: Record<string, string> = {};
    const allErrors: string[] = [];
    for (const entry of values) {
      const { id } = entry;
      const keyValue = fromObject[`key-${id}`] as string;
      const valueValue = fromObject[`value-${id}`] as string;
      if (!!keyValue.trim() && !!valueValue.trim()) {
        if (newValues[keyValue] != null) {
          allErrors.push(`key-${id}`);
        } else {
          newValues[keyValue] = valueValue;
        }
      }
    }
    if (allErrors.length > 0) {
      setErrors(allErrors);
      return;
    }
    onSelect(newValues);
    onClose(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogTrigger
        className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
      >
        <PencilIcon />
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            Create, edit, and delete {title} options.
          </DialogDescription>
        </DialogHeader>
        <form
          ref={formRef}
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit();
          }}
          className="w-full space-y-2"
        >
          <div className="flex items-center gap-2">
            <div className="w-1/2 px-2 text-sm">Key</div>
            <div className="w-1/2 px-2 text-sm">Value</div>
          </div>
          {values.map(({ id, key: k, value: v }, i) => {
            const keyName = `key-${id}`;
            const valueName = `value-${id}`;
            return (
              <div
                key={k}
                className="grid w-full grid-cols-[1fr_1fr_auto] items-start gap-2"
              >
                <div className="flex flex-col">
                  <Input
                    name={keyName}
                    defaultValue={k}
                    id={keyName}
                    onChange={() => {
                      if (errors.includes(keyName)) {
                        setErrors((prev) => prev.filter((v) => v != keyName));
                      }
                    }}
                    aria-invalid={errors.includes(keyName)}
                  />
                  {errors.includes(keyName) && (
                    <p className="text-destructive p-1 text-xs">Invalid Key</p>
                  )}
                </div>
                <div className="flex flex-col">
                  <Input
                    onChange={() => {
                      if (errors.includes(valueName)) {
                        setErrors((prev) => prev.filter((v) => v != valueName));
                      }
                    }}
                    name={valueName}
                    id={valueName}
                    defaultValue={v}
                    aria-invalid={errors.includes(valueName)}
                  />
                  {errors.includes(valueName) && (
                    <p className="text-destructive p-1 text-xs">
                      Invalid Value
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="destructiveOutline"
                  size="icon-sm"
                  onClick={() => {
                    setErrors((prev) =>
                      prev.filter((e) => e !== valueName && e !== keyName),
                    );
                    setValues((prev) => prev.filter((v) => v.id != id));
                  }}
                >
                  <Trash2Icon />
                </Button>
              </div>
            );
          })}
          <Button
            type="button"
            variant="ghost"
            className=""
            onClick={() => {
              setValues((prev) => [
                ...prev,
                {
                  id: randomAlphaUnderscore(20),
                  key: "",
                  value: "",
                },
              ]);
            }}
          >
            <PlusIcon /> Add Row
          </Button>
          <Button className="w-full">Save</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
};
