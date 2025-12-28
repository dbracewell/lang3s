"use client";
import { useRouter } from "next/navigation";
import { Button, buttonVariants } from "@/components/ui/button";
import React from "react";
import type { VariantProps } from "class-variance-authority";

export const GoBackButton = ({
  asChild,
  children,
  ...props
}: { children: React.ReactNode } & VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) => {
  const router = useRouter();
  return (
    <Button
      {...props}
      asChild={asChild}
      type="button"
      onClick={() => router.back()}
    >
      {children}
    </Button>
  );
};
