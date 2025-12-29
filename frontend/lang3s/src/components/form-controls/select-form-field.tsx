import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils/cn";
import { FieldValues, Path, UseFormReturn } from "react-hook-form";
import { RequiredField } from "@/components/form-controls/required-field";
import { RefObject } from "react";

type SelectOption = {
  label?: string;
  type: "group" | "item";
  className?: string;
};

export type SelectOptionItem = SelectOption & {
  type: "item";
  value: string;
  node?: React.ReactNode;
};

export type SelectOptionGroup = SelectOption & {
  type: "group";
  items: SelectOptionItem[];
};

type SelectData = SelectOptionItem | SelectOptionGroup;

type Props<T extends FieldValues> = {
  reactHookForm: UseFormReturn<T>;
  name: Path<T>;
  label?: string;
  description?: string;
  selectTriggerClassName?: string;
  selectContentClassName?: string;
  formItemClassName?: string;
  formLabelClassName?: string;
  formDescriptionClassName?: string;
  options: SelectData[];
  nullOption?: SelectOptionItem;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  onValueChange?: (value: string) => void;
  onFocus?: () => void;
  onBlur?: () => void;
  defaultValue?: string;
  ref?: RefObject<HTMLDivElement | null>;
};

export const SelectFormField = <T extends FieldValues>({
  reactHookForm,
  name,
  label,
  description,
  formItemClassName,
  formLabelClassName,
  formDescriptionClassName,
  selectTriggerClassName,
  selectContentClassName,
  nullOption,
  options,
  placeholder,
  onValueChange,
  disabled = false,
  required = false,
  onFocus,
  ref,
  onBlur,
  defaultValue,
}: Props<T>) => {
  const handleValueChange = (value: string) => {
    if (nullOption && nullOption.value === value) return null;
    return value;
  };

  return (
    <FormField
      name={name}
      control={reactHookForm.control}
      render={({ field }) => (
        <FormItem className={formItemClassName}>
          {label && (
            <FormLabel className={formLabelClassName}>
              {label} {required && <RequiredField />}
            </FormLabel>
          )}
          <Select
            defaultValue={defaultValue}
            value={field.value ?? defaultValue}
            onValueChange={(value) => {
              field.onChange(handleValueChange(value));
              onValueChange?.(value);
            }}
            disabled={disabled}
          >
            <FormControl>
              <SelectTrigger
                onFocus={onFocus}
                onBlur={onBlur}
                className={cn("w-full", selectTriggerClassName)}
              >
                <SelectValue placeholder={placeholder ?? ""} />
              </SelectTrigger>
            </FormControl>
            <SelectContent className={selectContentClassName} ref={ref}>
              {nullOption && (
                <SelectItem
                  value={nullOption.value}
                  className={nullOption.className}
                >
                  {nullOption.node
                    ? nullOption.node
                    : nullOption.label
                      ? nullOption.label
                      : nullOption.value}
                </SelectItem>
              )}
              {options.map((option, index) => (
                <SelectOption key={index} option={option} />
              ))}
            </SelectContent>
          </Select>
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

const SelectOption = ({ option }: { option: SelectData }) => {
  if (option.type === "item") {
    return (
      <SelectItem value={option.value} className={option.className}>
        {option.node ? option.node : option.label ? option.label : option.value}
      </SelectItem>
    );
  }

  return (
    <SelectGroup className={option.className}>
      {option.label && <SelectLabel>{option.label}</SelectLabel>}
      {option.items.map((child) => (
        <SelectOption key={child.value} option={child} />
      ))}
    </SelectGroup>
  );
};
