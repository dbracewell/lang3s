import { RequiredField } from "@/components/form-controls/required-field";
import { NumberInput } from "@/components/ui/number-input";
import {
   FormControl,
   FormDescription,
   FormField,
   FormItem,
   FormLabel,
   FormMessage,
} from "@/components/ui/form";
import React from "react";
import { FieldValues, Path, UseFormReturn } from "react-hook-form";

type Props<T extends FieldValues> = Omit<
   React.ComponentProps<typeof NumberInput>,
   "value" | "onChange"
> & {
   reactHookForm: UseFormReturn<T>;
   name: Path<T>;
   label?: string;
   formItemClassName?: string;
   formLabelClassName?: string;
   formDescriptionClassName?: string;
   description?: string;
   onChange?: (value: number | null) => void;
};

export const NumberInputFormField = <T extends FieldValues>({
   reactHookForm,
   name,
   label,
   formItemClassName,
   formLabelClassName,
   formDescriptionClassName,
   description,
   onChange,
   ...props
}: Props<T>) => {
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
                  <NumberInput
                     {...field}
                     {...props}
                     value={field.value}
                     onChange={(value) => {
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
