import {
   FormControl,
   FormDescription,
   FormField,
   FormItem,
   FormLabel,
   FormMessage,
} from "@/components/ui/form";
import {
   Popover,
   PopoverContent,
   PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { CalendarIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { FieldValues, Path, UseFormReturn } from "react-hook-form";
import { RequiredField } from "@/components/form-controls/required-field";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";

type Props<T extends FieldValues> = {
   reactHookForm: UseFormReturn<T>;
   name: Path<T>;
   label?: string;
   description?: string;
   formItemClassName?: string;
   formLabelClassName?: string;
   formDescriptionClassName?: string;
   className?: string;
   allowInFuture?: boolean;
   minDate?: Date;
   maxDate?: Date;
   disabled?: boolean;
   allowClear?: boolean;
   required?: boolean;
   onChange?: (value: Date | null) => void;
};

const formatDate = (date: Date) => {
   return new Intl.DateTimeFormat(undefined, {
      month: "short",
      year: "numeric",
      day: "2-digit",
   }).format(date);
};

export const DatePickerFormField = <T extends FieldValues>({
   reactHookForm,
   name,
   label,
   description,
   formItemClassName,
   formLabelClassName,
   formDescriptionClassName,
   className,
   allowInFuture = true,
   minDate = new Date("1900-01-01"),
   maxDate,
   disabled = false,
   allowClear = false,
   required = false,
   onChange,
}: Props<T>) => {
   const [isPopoverOpen, setIsPopoverOpen] = useState(false);

   const isDateDisabled = (date: Date): boolean => {
      const now = new Date();
      if (!allowInFuture && date > now) {
         return true;
      }
      if (minDate && date < minDate) {
         return true;
      }
      if (maxDate && date > maxDate) {
         return true;
      }
      return false;
   };

   return (
      <FormField
         name={name}
         control={reactHookForm.control}
         render={({ field }) => (
            <FormItem className={formItemClassName}>
               <div className="grid flex-1 gap-2">
                  {label && (
                     <FormLabel className={formLabelClassName}>
                        {label} {required && <RequiredField />}
                     </FormLabel>
                  )}
                  <div className="w-full flex items-center gap-2 justify-between">
                     <Popover
                        open={isPopoverOpen}
                        onOpenChange={setIsPopoverOpen}
                     >
                        <PopoverTrigger asChild>
                           <FormControl>
                              <Button
                                 disabled={disabled}
                                 type="button"
                                 onClick={() => setIsPopoverOpen(true)}
                                 className={cn(
                                    "pl-3 flex-1 text-left bg-transparent dark:bg-input/30  dark:hover:bg-input/40 text-foreground",
                                    !field.value && "text-muted-foreground",
                                    className
                                 )}
                              >
                                 {field.value ? (
                                    formatDate(field.value)
                                 ) : (
                                    <span>Select a Date</span>
                                 )}
                                 <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                              </Button>
                           </FormControl>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                           <Calendar
                              mode="single"
                              selected={field.value}
                              defaultMonth={field.value}
                              onSelect={(value) => {
                                 field.onChange(value ?? null);
                                 onChange?.(value ?? null);
                                 setIsPopoverOpen(false);
                              }}
                              disabled={isDateDisabled}
                              captionLayout="dropdown"
                           />
                        </PopoverContent>
                     </Popover>
                     {allowClear && field.value && (
                        <Button
                           variant="ghost"
                           className="bg-transparent hover:bg-destructive!  rounded-full hover:text-white text-destructive size-6! shadow-none"
                           onClick={() => field.onChange(null)}
                        >
                           <XIcon className="size-4 " />
                        </Button>
                     )}
                  </div>
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
