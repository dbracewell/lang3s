import { cn } from "@/lib/utils";
import React from "react";

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
        "flex min-h-0 flex-1 flex-col overflow-clip rounded-md border pb-5",
        className,
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
        "mb-4 w-full border-b-2 bg-gradient-to-b from-zinc-50 to-zinc-100 py-3 text-center",
        className,
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
    <div className="scrollable flex-1">
      <div className={cn("flex flex-col", className)}>{children}</div>
    </div>
  );
};

export const ScrollableBox = {
  Container,
  Header,
  ScrollArea,
};
