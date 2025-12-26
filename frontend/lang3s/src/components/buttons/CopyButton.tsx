"use client";
import { Button, buttonVariants } from "@/components/ui/button";
import { VariantProps } from "class-variance-authority";
import { CopyCheckIcon, CopyIcon } from "lucide-react";
import { useEffect, useState } from "react";

export const CopyButton = ({
  text,
  className,
  variant = "ghost",
  size = "icon",
}: {
  text: string;
  className?: string;
  variant?: VariantProps<typeof buttonVariants>["variant"];
  size?: VariantProps<typeof buttonVariants>["size"];
}) => {
  const [copied, setCopied] = useState(false);

  const onCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
  };

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1000);
    return () => clearTimeout(timer);
  }, [copied, setCopied]);
  return (
    <Button
      variant={variant}
      size={size}
      disabled={copied}
      onClick={onCopy}
      className={className}
    >
      {copied ? <CopyCheckIcon /> : <CopyIcon />}
    </Button>
  );
};
