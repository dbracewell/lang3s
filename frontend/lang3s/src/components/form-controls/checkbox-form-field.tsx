import { cn } from "@/lib/utils";
import { RequiredField } from "@/components/form-controls/required-field";
import { Checkbox } from "@/components/ui/checkbox";
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

type Props<T extends FieldValues> = React.ComponentProps<typeof Checkbox> & {
   reactHookForm: UseFormReturn<T>;
   name: Path<T>;
   label: string;
   description?: string;
   formItemClassName?: string;
   formLabelClassName?: string;
   formDescriptionClassName?: string;
   formLabelValueContainerClassName?: string;
   labelPosition?: "left" | "right" | "top" | "bottom";
};

export const CheckboxFormField = <T extends FieldValues>({
   reactHookForm,
   name,
   label,
   formItemClassName,
   formLabelClassName,
   formDescriptionClassName,
   formLabelValueContainerClassName,
   description,
   labelPosition = "right",
   ...props
}: Props<T>) => {
   return (
      <FormField
         name={name}
         control={reactHookForm.control}
         render={({ field }) => (
            <FormItem className={formItemClassName}>
               <div
                  className={cn(
                     "flex items-center gap-y-1 gap-x-2",
                     (labelPosition === "top" || labelPosition === "bottom") &&
                        "flex-col",
                     formLabelValueContainerClassName
                  )}
               >
                  {(labelPosition === "top" || labelPosition === "left") && (
                     <FormLabel className={formLabelClassName}>
                        {label} {props.required && <RequiredField />}
                     </FormLabel>
                  )}
                  <FormControl>
                     <Checkbox
                        {...field}
                        {...props}
                        checked={field.value ?? false}
                        onCheckedChange={(checked) => {
                           field.onChange(checked);
                           props.onCheckedChange?.(checked);
                        }}
                     />
                  </FormControl>
                  {(labelPosition === "bottom" ||
                     labelPosition === "right") && (
                     <FormLabel className={formLabelClassName}>
                        {label} {props.required && <RequiredField />}
                     </FormLabel>
                  )}
               </div>
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
