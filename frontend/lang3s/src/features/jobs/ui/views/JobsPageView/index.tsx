"use client";
import DataTableProvider from "@/components/data-table/DataTableContext";
import { useDataTable } from "@/components/data-table/use-data-table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { FilterDialog } from "@/features/jobs/ui/views/JobsPageView/FilterDialog";
import { Trash2Icon, XIcon } from "lucide-react";
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { columns } from "./columns";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { useJobStatusSync } from "@/features/jobs/hooks/jobStatusSync";
import { useSetAtom } from "jotai";
import { removeJobStatusAtom } from "@/features/events/stores/job-stores";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  jobsDeleteJobMutation,
  jobsListJobsOptions,
} from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { JobListResponse } from "@/clients/core";

export const JobPageView = () => {
  const { data, refetch } = useQuery({
    ...jobsListJobsOptions({
      client: coreClient,
    }),
  });
  const [, setCurrentTime] = useState<number>(0);
  const remove = useSetAtom(removeJobStatusAtom);
  useJobStatusSync(data, refetch);

  useEffect(() => {
    const i = setInterval(() => setCurrentTime(Date.now), 1000);
    return () => clearInterval(i);
  }, []);

  const [toDelete, setToDelete] = useState<number[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);

  const deleteJobMutation = useMutation({
    ...jobsDeleteJobMutation({
      client: coreClient,
    }),
  });

  const deleteSelected = async () => {
    let failed = 0;
    for (const id of toDelete) {
      try {
        await deleteJobMutation.mutateAsync({
          path: {
            job_id: id,
          },
        });
      } catch {
        failed += 1;
      }
    }

    if (failed > 0) {
      toast.error(`Could not delete ${failed} jobs`);
    } else {
      toast.success(`Successfully deleted ${toDelete.length} jobs!`);
      remove(toDelete);
    }
    setToDelete([]);
    setIsDeleting(false);
  };

  const { DataTable, setFilter, getFilter, rows } = useDataTable({
    columns,
    getRowId: (row) => String(row.id),
    data: data ?? ([] as JobListResponse),
    initialSortColumn: "id",
    appearance: {
      sortButton: "text-white bg-white/30",
      container: "shadow bg-card rounded-xl h-full border",
      headerRow: "bg-heading divide-x text-white text-center",
      headerCell: "p-2",
      bodyCell: "p-1 h-10",
      bodyRow: "border-b divide-x even:bg-alternate-row bg-row",
    },
  });

  return (
    <ScrollableBox.Container className="m-1 gap-2">
      <ScrollableBox.Header>
        <h1>Jobs</h1>
        <p className="pageSubheading">View and manage jobs.</p>
      </ScrollableBox.Header>
      <div className="flex items-center justify-between px-1">
        <div className="flex flex-col items-center gap-1">
          {isDeleting ? (
            <div className="flex items-center gap-2 rounded-lg border bg-slate-300/50 p-1 shadow dark:bg-slate-700/50">
              <Checkbox
                id="selectAll"
                onCheckedChange={(e) => {
                  if (!e) {
                    setToDelete([]);
                  } else {
                    setToDelete(rows.map((e) => e.id));
                  }
                }}
              />{" "}
              <Label htmlFor="selectAll">Select All</Label>
              <Button
                variant="ghost"
                disabled={deleteJobMutation.isPending}
                size="icon-sm"
                onClick={() => {
                  setToDelete([]);
                  setIsDeleting(false);
                }}
              >
                <XIcon />
              </Button>
              <LoadingButton
                variant="destructive"
                size="icon-sm"
                onClick={() => deleteSelected()}
                isLoading={deleteJobMutation.isPending}
              >
                <Trash2Icon />
              </LoadingButton>
            </div>
          ) : (
            <div className="p-0.75">
              <Button
                variant="listButton"
                size="sm"
                onClick={() => setIsDeleting((p) => !p)}
              >
                <Trash2Icon /> Bulk Delete
              </Button>
            </div>
          )}
        </div>
        <FilterDialog getFilter={getFilter} setFilter={setFilter} />
      </div>
      <DataTableProvider
        columns={columns}
        context={{ toDelete, setToDelete, isDeleting }}
      >
        {DataTable}
      </DataTableProvider>
    </ScrollableBox.Container>
  );
};
