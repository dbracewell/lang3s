"use client";
import React from "react";
import { jobStatusByIdAtom } from "@/features/events/stores/job-stores";
import { useAtomValue } from "jotai";
import { Job } from "@/clients/core";
import { formatDuration } from "@/lib/utils/formatters";

export const ElapsedTimeCell = ({ row }: { row: Job }) => {
  const job = useAtomValue(jobStatusByIdAtom(row.id));
  const started_at = job?.started_at ?? row.started_at;
  if (started_at == null) {
    return <div>-</div>;
  }
  const end_time_raw = job?.completed_at ?? row.completed_at;
  const end_time_date = end_time_raw ? Date.parse(end_time_raw) : Date.now();
  const elapsed = formatDuration(end_time_date - Date.parse(started_at));
  return <div>{elapsed}</div>;
};
