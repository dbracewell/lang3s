import { cn } from "@/lib/utils";
import React from "react";
import {
   ScrollBar,
   ScrollArea as ShadCNScrollArea,
} from "@/components/ui/scroll-area";

const Container = ({
   children,
   className,
}: {
   children: React.ReactNode;
   className?: string;
}) => {
   return (
      <div
         className={cn(
            "flex-1 min-h-0 border rounded-md pb-5 flex flex-col overflow-clip",
            className
         )}
      >
         {children}
      </div>
   );
};

const Header = ({
   children,
   className,
}: {
   children: React.ReactNode;
   className?: string;
}) => {
   return (
      <h1
         className={cn(
            "border-b-2 py-3 w-full text-center bg-gradient-to-b from-zinc-50 to-zinc-100 mb-4",
            className
         )}
      >
         {children}
      </h1>
   );
};

const ScrollArea = ({
   children,
   className,
}: {
   children: React.ReactNode;
   className?: string;
}) => {
   return (
      <ShadCNScrollArea className="flex-1 min-h-0" type="always">
         <div className={cn("flex flex-col", className)}>{children}</div>
      </ShadCNScrollArea>
   );
};

export const ScrollableBox = {
   Container,
   Header,
   ScrollArea,
};
