import { RequiredField } from "@/components/form-controls/required-field";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import React, { ChangeEvent } from "react";
import {
  FieldArrayWithId,
  FieldValues,
  Path,
  UseFormReturn,
} from "react-hook-form";

type Props<T extends FieldValues> = Omit<
  React.ComponentProps<typeof Input>,
  "value" | "onChange"
> & {
  reactHookForm: UseFormReturn<T>;
  name: Path<T>;
  label?: string;
  emptyToNull?: boolean;
  formItemClassName?: string;
  formLabelClassName?: string;
  formDescriptionClassName?: string;
  description?: string;
  onChange?: (value: string | Date | null) => void;
};

export const InputFormField = <T extends FieldValues>({
  reactHookForm,
  name,
  label,
  type,
  formItemClassName,
  formLabelClassName,
  formDescriptionClassName,
  emptyToNull = false,
  description,
  onChange,
  ...props
}: Props<T>) => {
  const handleOnChange = (e: ChangeEvent<HTMLInputElement>) => {
    switch (type) {
      case "text":
        const textValue = e.target.value;
        if (emptyToNull && !textValue.trim()) {
          return null;
        }
        return textValue;
      case "date":
      case "datetime-local":
      case "time":
        return e.target.valueAsDate;
    }
    return e.target.value;
  };

  return (
    <FormField
      name={name}
      control={reactHookForm.control}
      render={({ field }) => (
        <FormItem className={formItemClassName}>
          {label && (
            <FormLabel className={formLabelClassName}>
              {label} {props.required && <RequiredField />}
            </FormLabel>
          )}
          <FormControl>
            <Input
              {...field}
              {...props}
              type={type}
              value={field.value ?? ""}
              onChange={(e) => {
                const value = handleOnChange(e);
                field.onChange(value);
                onChange?.(value);
              }}
            />
          </FormControl>
          {description && (
            <FormDescription className={formDescriptionClassName}>
              {description}
            </FormDescription>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  );
};
