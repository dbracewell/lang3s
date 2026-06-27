"use client";
import { Progress } from "@/components/ui/progress";
import React from "react";
import { jobStatusByIdAtom } from "@/features/events/stores/job-stores";
import { useAtomValue } from "jotai";
import { Job } from "@/clients/core";

export const ProgressCell = ({ row }: { row: Job }) => {
  const job = useAtomValue(jobStatusByIdAtom(row.id));
  const pct = Math.floor(
    job?.progress ??
      (row.total > 0 ? (row.completed + row.failed) / row.total : 0) * 100,
  ).toFixed(0);
  return (
    <div className="relative flex w-full items-center">
      <Progress value={Number(pct)} />
      <div
        className="border-dodger-blue-600 bg-dodger-blue-600 absolute top-1/2 w-10 -translate-y-1/2 rounded-sm border p-0.5 text-center text-xs text-white shadow"
        style={{
          left: `min( max( ${pct}% - 30px , 3px ), 100% - 40px )`,
        }}
      >
        {pct}%
      </div>
    </div>
  );
};
