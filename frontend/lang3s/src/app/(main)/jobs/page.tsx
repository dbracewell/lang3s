"use client";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { caller } from "@/trpc/server";
import { useTRPCQuery } from "@/trpc/use-queries";
import {
  CircleCheck,
  CircleCheckIcon,
  CircleXIcon,
  ClockIcon,
  CogIcon,
  LoaderCircleIcon,
} from "lucide-react";
import React from "react";

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

const JobsPage = () => {
  const { data } = useTRPCQuery((trpc) =>
    trpc.jobs.getAll.queryOptions(
      {},
      {
        refetchInterval: 1000,
      },
    ),
  );
  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-1 flex-col gap-2 p-5">
      <div className="flex-1 overflow-clip rounded-lg border bg-white shadow">
        <div className="bg-dodger-blue-500 grid grid-cols-[0.4fr_1.5fr_1fr_1fr_1.5fr] gap-1 divide-x divide-slate-300 border-b text-center font-semibold text-white">
          <div className="p-2">Job Id</div>
          <div className="p-2">Job Name</div>
          <div className="p-2">Job Status</div>
          <div className="p-2">Started</div>
          <div className="p-2">Job Progress</div>
        </div>
        <div className="divide-y last:border-b">
          {data?.map((job, i) => {
            const pct = Math.floor(
              (job.total > 0 ? job.completed / job.total : 0) * 100,
            );
            return (
              <div
                key={job.id}
                className={cn(
                  "grid grid-cols-[0.4fr_1.5fr_1fr_1fr_1.5fr] divide-x divide-slate-300",
                  i % 2 == 1 && "bg-slate-200",
                )}
              >
                <div className="p-2 text-center">{job.id}</div>
                <div className="p-2 text-center">{job.name}</div>
                <div
                  className={cn(
                    "flex items-center justify-center gap-2 p-2 text-center font-medium text-zinc-700 uppercase",
                    job.status === "processing" &&
                      "bg-dodger-blue-300 text-dodger-blue-800",
                    job.status === "complete" && "bg-green-300 text-green-800",
                    job.status === "failed" && "bg-red-300 text-red-800",
                  )}
                >
                  {getIcon(job.status)}
                  {job.status}
                </div>
                <div className="p-2 text-center">
                  {new Intl.DateTimeFormat("en-US", {
                    dateStyle: "short",
                    timeStyle: "short",
                  }).format(job.createdAt!)}
                </div>
                <div className="relative flex items-center gap-2 p-2 px-4">
                  <Progress value={pct} />
                  <div
                    className="border-dodger-blue-600 bg-dodger-blue-600 absolute top-1/2 w-10 -translate-y-1/2 rounded-sm border p-0.5 text-center text-xs text-white shadow"
                    style={{
                      left: `min( max( ${pct}% - 30px , 3px ), 100% - 50px )`,
                    }}
                  >
                    {pct}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default JobsPage;
