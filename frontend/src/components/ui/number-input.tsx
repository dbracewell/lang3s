import { Input } from "@/components/ui/input";
import React, { ChangeEvent } from "react";

export const NumberInput = ({
   className,
   value,
   onChange,
   min,
   max,
   ...props
}: Omit<
   React.ComponentProps<typeof Input>,
   "type" | "onChange" | "value" | "min" | "max"
> & {
   value: number | null | undefined;
   onChange: (value: number | null) => void;
   min?: number | null;
   max?: number | null;
}) => {
   const handleOnChange = (e: ChangeEvent<HTMLInputElement>) => {
      const numberValue = e.target.valueAsNumber;
      if (isFinite(numberValue)) {
         let returnValue = numberValue;
         if (min != null && numberValue <= min) returnValue = min;
         if (max != null && numberValue >= max) returnValue = max;
         onChange?.(returnValue);
      } else {
         onChange?.(null);
      }
   };

   return (
      <Input
         type="number"
         {...props}
         value={value ?? ""}
         onChange={handleOnChange}
         className={className}
      />
   );
};
