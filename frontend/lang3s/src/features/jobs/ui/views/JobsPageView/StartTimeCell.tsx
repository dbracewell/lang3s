"use client";
import React from "react";
import { jobStatusByIdAtom } from "@/features/events/stores/job-stores";
import { useAtomValue } from "jotai";
import { Job } from "@/clients/core";

export const StartTimeCell = ({ row }: { row: Job }) => {
  const job = useAtomValue(jobStatusByIdAtom(row.id));
  const started_at = job?.started_at ?? row.started_at;
  return (
    <p className="text-center whitespace-pre-line">
      {started_at != null
        ? new Intl.DateTimeFormat("en-US", {
            dateStyle: "short",
            timeStyle: "short",
          }).format(Date.parse(started_at))
        : "-"}
    </p>
  );
};
