"use client";
import DataTableProvider from "@/components/data-table/DataTableContext";
import { useDataTable } from "@/components/data-table/use-data-table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { FilterDialog } from "@/features/jobs/ui/views/JobsPageView/FilterDialog";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Trash2Icon, XIcon } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { columns, type JobType } from "./columns";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { AddUserDialog } from "@/features/auth/ui/views/AdminUsersPageView/AddUserDialog";
import { useUser } from "@/features/auth/UserContext";
import {
  PagePermissions,
  roleHasPermissions,
} from "@/features/auth/permissions";
import { redirect } from "next/navigation";

export const JobPageView = () => {
  const user = useUser();
  const hasPermissions = roleHasPermissions(
    user.role,
    PagePermissions['"/system/jobs"'],
  );

  const { data, refetch } = useTRPCQuery((trpc) =>
    trpc.jobs.getAll.queryOptions(),
  );

  useEffect(() => {
    const intervalId = setInterval(() => refetch(), 5000);
    return () => clearInterval(intervalId);
  }, []);

  const [toDelete, setToDelete] = useState<number[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);

  const deleteJobMutation = useTRPCMutation((trpc) => ({
    mutation: trpc.jobs.delete.mutationOptions({}),
  }));

  const deleteSelected = async () => {
    let failed = 0;
    for (const id of toDelete) {
      try {
        await deleteJobMutation.mutateAsync({ job_id: id });
      } catch {
        failed += 1;
      }
    }
    setToDelete([]);
    setIsDeleting(false);
    if (failed > 0) {
      toast.error(`Could not delete ${failed} jobs`);
    }
  };

  const { DataTable, setFilter, getFilter, rows } = useDataTable({
    columns,
    data: data ?? ([] as JobType[]),
    initialSortColumn: "id",
    appearance: {
      sortButton: "text-white bg-white/30",
      container: "shadow bg-card rounded-xl",
      headerRow: "bg-heading divide-x text-white text-center",
      headerCell: "p-2",
      bodyCell: "p-1 h-10",
      bodyRow: "border-b divide-x even:bg-alternate-row bg-row",
    },
  });

  if (!hasPermissions) {
    redirect("/");
    return null;
  }

  return (
    <ScrollableBox.Container className="gap-2">
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
            <div className="p-[3px]">
              <Button
                variant="listButton"
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
        <DataTable />
      </DataTableProvider>
    </ScrollableBox.Container>
  );
};
