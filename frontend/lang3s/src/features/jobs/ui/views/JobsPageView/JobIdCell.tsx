"use client";
import { useDataTableContext } from "@/components/data-table/DataTableContext";
import { Checkbox } from "@/components/ui/checkbox";
import { LoadingButton } from "@/components/ui/loading-button";
import { Trash2Icon } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsDeleteJobMutation } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { useRouter } from "next/navigation";

export const JobIdCell = ({ id }: { id: number }) => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const deleteJobMutation = useMutation({
    ...jobsDeleteJobMutation({
      client: coreClient,
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.refresh();
      toast.success("Job deleted successfully.");
    },
    onError: () => toast.error("Job deleted failed"),
  });
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
            onClick={() => deleteJobMutation.mutate({ path: { job_id: id } })}
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
