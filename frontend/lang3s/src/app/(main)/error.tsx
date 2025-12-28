"use client";
import { TRPCError } from "@trpc/server";
import { OctagonAlertIcon } from "lucide-react";
import React from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

const ErrorPage = ({ error }: { error: unknown }) => {
  let message = null;
  if (error instanceof TRPCError) {
    message = error.code;
  } else if (error instanceof Error) {
    message = error.message;
  }
  const router = useRouter();
  return (
    <div className="flex h-full flex-1 items-center justify-center">
      <div className="flex max-w-2xl flex-col items-center gap-2 rounded-lg border bg-white p-15 shadow">
        <div className="text-destructive flex items-center gap-2 text-2xl font-bold">
          <OctagonAlertIcon className="size-20" />
          <p>Something went wrong</p>
        </div>
        {!!message && (
          <p className="text-muted-foreground text-sm">Error: {message}</p>
        )}
        <Button onClick={() => router.refresh()}>Try Again</Button>
      </div>
    </div>
  );
};

export default ErrorPage;
