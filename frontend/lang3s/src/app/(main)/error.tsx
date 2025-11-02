"use client";
import { TRPCError } from "@trpc/server";
import { OctagonAlertIcon } from "lucide-react";
import React from "react";

const ErrorPage = ({ error }: { error: unknown }) => {
  let message = null;
  if (error instanceof TRPCError) {
    message = error.code;
  } else if (error instanceof Error) {
    message = error.message;
  }
  return (
    <div className="flex h-full flex-1 items-center justify-center">
      <div className="flex flex-col items-center gap-2 rounded-lg border bg-white p-15 shadow">
        <div className="text-destructive flex items-center gap-2 text-2xl font-bold">
          <OctagonAlertIcon className="size-20" />
          <p>Something went wrong</p>
        </div>
        {!!message && (
          <pre className="text-muted-foreground text-sm">Error: {message}</pre>
        )}
      </div>
    </div>
  );
};

export default ErrorPage;
