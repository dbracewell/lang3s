"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { VariantProps } from "class-variance-authority";
import { useRef, useState } from "react";

export function useConfirmationDialog({
  title,
  description,
  confirmVariant,
}: {
  title: string;
  description: string;
  confirmVariant?: VariantProps<typeof buttonVariants>["variant"];
}) {
  const [open, setOpen] = useState(false);
  const resolver = useRef<(value: boolean) => void>(null);

  const confirm = () => {
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  };

  const handleConfirm = () => {
    resolver.current?.(true);
    setOpen(false);
  };

  const handleCancel = () => {
    resolver.current?.(false);
    setOpen(false);
  };

  const Dialog = () => (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction variant={confirmVariant} onClick={handleConfirm}>
            Confirm
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  return { confirm, Dialog };
}
