"use client";
import { ColumnDef } from "@/components/data-table/data-table-types";
import { StringStartsWith } from "@/components/data-table/FilterFunctions";
import { JobIdCell } from "@/features/jobs/ui/views/JobsPageView/JobIdCell";
import { StatusCell } from "@/features/jobs/ui/views/JobsPageView/StatusCell";
import { Button } from "@/components/ui/button";
import { RefreshCcwIcon } from "lucide-react";
import { Job } from "@/clients/core";
import React from "react";
import { formatDuration } from "@/lib/utils/formatters";
import { Progress } from "@/components/ui/progress";

const ProgressHeader = () => {
  return (
    <div className="flex items-center justify-between">
      <span>Progress</span>
      <Button
        variant="ghost"
        type="button"
        className="ml-2"
        size="icon-xs"
        onClick={() => window.location.reload()}
      >
        <RefreshCcwIcon />
      </Button>
    </div>
  );
};

export const columns: ColumnDef<Job>[] = [
  {
    name: "id",
    sortFn: (a, b) => a.id - b.id,
    align: "center",
    size: "75px",
    cell: ({ row }) => JobIdCell({ id: row.id }),
  },
  {
    name: "name",
    align: "left",
    sortFn: (a, b) => (a.name < b.name ? -1 : 1),
    filterFn: StringStartsWith((row) => row.name),
    size: "minmax(300px, 1fr)",
    cell: ({ row }) => (
      <div className="flex items-center truncate">{row.name}</div>
    ),
  },
  {
    name: "status",
    align: "center",
    size: "150px",
    sortFn: (a, b) => (a.status < b.status ? -1 : 1),
    cellClassName: "p-0! h-full",
    filterFn: StringStartsWith((row) => row.status),
    cell: ({ row }) => StatusCell({ row }),
  },
  {
    name: "startTime",
    header: "Start Time",
    align: "center",
    cellClassName: "items-center",
    sortFn: (a, b) => {
      if (a.started_at) {
        if (b.started_at) {
          return Date.parse(a.started_at) - Date.parse(b.started_at);
        }
        return -1;
      }
      return 1;
    },
    size: "200px",
    cell: ({ row }) => (
      <p className="text-center whitespace-pre-line">
        {row.started_at != null
          ? new Intl.DateTimeFormat("en-US", {
              dateStyle: "short",
              timeStyle: "short",
            }).format(Date.parse(row.started_at))
          : "-"}
      </p>
    ),
  },
  {
    name: "elapsed",
    size: "100px",
    align: "center",
    cellClassName: "items-center",
    cell: ({ row }) => {
      const started_at = row.started_at;
      if (started_at == null) {
        return <div>-</div>;
      }
      const end_time_date = row.completed_at
        ? Date.parse(row.completed_at)
        : Date.now();
      const elapsed = formatDuration(end_time_date - Date.parse(started_at));
      return <div>{elapsed}</div>;
    },
  },
  {
    name: "progress",
    align: "center",
    size: "minmax(250px, 1fr)",
    header: <ProgressHeader />,
    sortFn: (a, b) => {
      const aPct = Math.floor((a.total > 0 ? a.completed / a.total : 0) * 100);
      const bPct = Math.floor((b.total > 0 ? b.completed / b.total : 0) * 100);
      return aPct - bPct;
    },
    cellClassName: "h-full!",
    cell: ({ row }) => {
      const pct = Math.floor(
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
    },
  },
];
