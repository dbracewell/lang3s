import { cn } from "@/lib/utils/cn";
import React from "react";

const Container = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
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
    <div className={cn("mb-4 flex w-full flex-col gap-1", className)}>
      {children}
    </div>
  );
};

const Footer = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn("flex w-full flex-col gap-1", className)}>
      {children}
    </div>
  );
};

const ScrollArea = ({
  children,
  className,
  outerClassName,
  ...props
}: React.ComponentProps<"div"> & {
  outerClassName?: string;
}) => {
  return (
    <div
      className={cn("scrollable flex-1 rounded-lg border p-2", outerClassName)}
      {...props}
    >
      <div className={cn("flex flex-col", className)}>{children}</div>
    </div>
  );
};

export const ScrollableBox = {
  Container,
  Header,
  Footer,
  ScrollArea,
};
