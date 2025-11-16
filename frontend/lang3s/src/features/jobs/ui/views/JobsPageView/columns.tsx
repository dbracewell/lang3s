"use client";
import { ColumnDef } from "@/components/data-table/data-table-types";
import { StringStartsWith } from "@/components/data-table/FilterFunctions";
import { formatDuration } from "@/lib/formatters";
import { JobIdCell } from "@/features/jobs/ui/views/JobsPageView/JobIdCell";
import { ProgressCell } from "@/features/jobs/ui/views/JobsPageView/ProgressCell";
import { StatusCell } from "@/features/jobs/ui/views/JobsPageView/StatusCell";
import { RouterOutputs } from "@/trpc/types";

export type JobType = RouterOutputs["jobs"]["getAll"][number];
export const columns: ColumnDef<JobType>[] = [
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
      if (a.startedAt) {
        if (b.startedAt) {
          return a.startedAt.getTime() - b.startedAt.getTime();
        }
        return -1;
      }
      return 1;
    },
    size: "200px",
    cell: ({ row }) => (
      <p className="text-center whitespace-pre-line">
        {row.startedAt
          ? new Intl.DateTimeFormat("en-US", {
              dateStyle: "short",
              timeStyle: "short",
            }).format(row.startedAt)
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
      if (row.startedAt == null) {
        return <div>-</div>;
      }
      const endTime = row.completedAt ?? new Date();
      const elapsed = formatDuration(
        endTime.getTime() - row.startedAt.getTime(),
      );
      return <div>{elapsed}</div>;
    },
  },
  {
    name: "progress",
    align: "center",
    size: "minmax(250px, 1fr)",
    sortFn: (a, b) => {
      const aPct = Math.floor((a.total > 0 ? a.completed / a.total : 0) * 100);
      const bPct = Math.floor((b.total > 0 ? b.completed / b.total : 0) * 100);
      return aPct - bPct;
    },
    cellClassName: "h-full!",
    cell: ({ row }) => <ProgressCell row={row} />,
  },
];
