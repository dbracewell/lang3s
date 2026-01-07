"use client";
import { cn } from "@/lib/utils/cn";
import { RouterOutputs } from "@/lib/trpc/types";
import {
  CircleCheckIcon,
  CircleXIcon,
  ClockIcon,
  LoaderCircleIcon,
} from "lucide-react";
import React from "react";
import { useAtomValue } from "jotai";
import { jobStatusByIdAtom } from "@/features/events/stores/job-stores";

const getIcon = (status: string) => {
  if (status === "processing") {
    return <LoaderCircleIcon className="animate-spin" />;
  }
  if (status === "complete") {
    return <CircleCheckIcon />;
  }
  if (status === "failed") {
    return <CircleXIcon />;
  }

  return <ClockIcon />;
};

export const StatusCell = ({
  row,
}: {
  row: RouterOutputs["jobs"]["getAll"][number];
}) => {
  const job = useAtomValue(jobStatusByIdAtom(row.id));
  const jobStatus = job?.status ?? row.status;
  return (
    <div
      className={cn(
        "flex w-full items-center justify-center gap-2 text-center font-medium text-zinc-700 uppercase [&_>svg]:h-4",
        row.status === "processing" &&
          "bg-dodger-blue-300 text-dodger-blue-800",
        row.status === "complete" && "bg-green-300 text-green-800",
        row.status === "failed" && "bg-red-300 text-red-800",
        row.status === "waiting" && "bg-gray-500 text-white",
      )}
    >
      {getIcon(jobStatus)}
      {jobStatus}
    </div>
  );
};
