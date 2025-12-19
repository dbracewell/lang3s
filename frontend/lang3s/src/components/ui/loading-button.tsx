import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { Loader2Icon } from "lucide-react";
import React from "react";

type LoadingButtonProps = React.ComponentProps<typeof Button> & {
  isLoading: boolean;
};

export const LoadingButton = ({
  className,
  variant,
  size,
  asChild = false,
  isLoading,
  children,
  ...props
}: LoadingButtonProps) => {
  return (
    <Button
      variant={variant}
      size={size}
      asChild={asChild}
      className={cn(
        "grid grid-cols-1 items-center justify-items-center",
        className,
      )}
      {...props}
    >
      <div
        className={cn(
          "col-start-1 col-end-1 row-start-1 row-end-1",
          isLoading ? "invisible" : "visible",
          className,
        )}
      >
        {children}
      </div>
      <div
        className={cn(
          "col-start-1 col-end-1 row-start-1 row-end-1",
          isLoading ? "visible" : "invisible",
        )}
      >
        <Loader2Icon className="animate-spin" />
      </div>
    </Button>
  );
};
