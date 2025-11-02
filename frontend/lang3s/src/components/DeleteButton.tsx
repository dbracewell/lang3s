"use client";
import { buttonVariants } from "@/components/ui/button";
import { LoadingButton } from "@/components/ui/loading-button";
import { VariantProps } from "class-variance-authority";
import { Trash2Icon } from "lucide-react";

export const DeleteButton = ({
  onDelete,
  isDeleting,
  className,
  variant = "destructiveOutline",
  size = "icon",
}: {
  onDelete: () => void;
  isDeleting: boolean;
  className?: string;
  variant?: VariantProps<typeof buttonVariants>["variant"];
  size?: VariantProps<typeof buttonVariants>["size"];
}) => {
  return (
    <LoadingButton
      isLoading={isDeleting}
      disabled={isDeleting}
      className={className}
      variant={variant}
      size={size}
      onClick={onDelete}
    >
      <Trash2Icon />
    </LoadingButton>
  );
};
