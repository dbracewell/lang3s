"use client";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";
import {
  jobStatusAtom,
  removeJobStatusAtom,
} from "@/features/events/stores/job-stores";

export function useJobStatusSync(
  data: { id: number }[] | undefined,
  refetch: () => Promise<any>,
) {
  const status = useAtomValue(jobStatusAtom);
  const remove = useSetAtom(removeJobStatusAtom);

  useEffect(() => {
    if (!status.length || data == null) return;

    const completed = status.filter(
      (j) => j.status === "complete" || j.status === "failed",
    );

    const newJobs = status.filter(
      (job) => data.find((e) => e.id === job.jobId) == null,
    );

    if (completed.length > 0) {
      refetch().then(() => {
        remove(completed.map((j) => j.jobId));
      });
    } else if (newJobs.length > 0) {
      refetch();
    }
  }, [status, data, refetch, remove]);
}
