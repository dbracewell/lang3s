"use client";
import { useDataTableContext } from "@/components/data-table/DataTableContext";
import { Checkbox } from "@/components/ui/checkbox";
import { LoadingButton } from "@/components/ui/loading-button";
import { useTRPCMutation } from "@/trpc/use-mutation";
import { Trash2Icon } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { toast } from "sonner";

export const JobIdCell = ({ id }: { id: number }) => {
  const deleteJobMutation = useTRPCMutation((trpc) => ({
    mutation: trpc.jobs.delete.mutationOptions({
      onSuccess: (data) =>
        toast.success(`Successfully deleted Job #${data.id}`),
      onError: () => toast.error("Failed to delete job"),
    }),
  }));
  const { context } = useDataTableContext();
  const inCheck = context.isDeleting as boolean;
  return (
    <div className="group flex items-center justify-center">
      {inCheck && (
        <Checkbox
          className="mr-1"
          checked={(context.toDelete as number[]).includes(id)}
          onCheckedChange={(e) => {
            const setToDelete = context.setToDelete as Dispatch<
              SetStateAction<number[]>
            >;
            if (e) {
              setToDelete((p) => [...p, id]);
            } else {
              setToDelete((p) => p.filter((v) => v !== id));
            }
          }}
        />
      )}
      {!inCheck && (
        <>
          <span className="group-hover:hidden">{id}</span>
          <LoadingButton
            onClick={() => deleteJobMutation.mutate({ job_id: id })}
            disabled={deleteJobMutation.isPaused}
            className="hidden group-hover:grid"
            variant="destructive"
            size="icon-sm"
            isLoading={deleteJobMutation.isPending}
          >
            <Trash2Icon />
          </LoadingButton>
        </>
      )}
    </div>
  );
};
