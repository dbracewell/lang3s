import { RequiredField } from "@/components/form-controls/required-field";
import {
   FormControl,
   FormDescription,
   FormField,
   FormItem,
   FormLabel,
   FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";
import React, { ChangeEvent } from "react";
import { FieldValues, Path, UseFormReturn } from "react-hook-form";

type Props<T extends FieldValues> = React.ComponentProps<"textarea"> & {
   reactHookForm: UseFormReturn<T>;
   name: Path<T>;
   label?: string;
   emptyToNull?: boolean;
   formItemClassName?: string;
   formLabelClassName?: string;
   formDescriptionClassName?: string;
   description?: string;
};

export const TextareaFormField = <T extends FieldValues>({
   reactHookForm,
   name,
   label,
   formItemClassName,
   formLabelClassName,
   formDescriptionClassName,
   emptyToNull = false,
   description,
   ...props
}: Props<T>) => {
   const handleOnChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
      const str = e.target.value;
      if (emptyToNull && !str.trim()) {
         return null;
      }
      return str;
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
                  <Textarea
                     {...field}
                     {...props}
                     value={field.value ?? ""}
                     onChange={(e) => field.onChange(handleOnChange(e))}
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
