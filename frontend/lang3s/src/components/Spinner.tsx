import { LoaderCircleIcon } from "lucide-react";
import React from "react";

export const Spinner = () => {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center">
      <LoaderCircleIcon className="text-dodger-blue-500 size-20 animate-spin" />
      <span className="animate-pulse text-lg font-bold">Loading...</span>
    </div>
  );
};
