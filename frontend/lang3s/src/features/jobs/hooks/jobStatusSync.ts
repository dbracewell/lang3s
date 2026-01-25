"use client";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect, useRef } from "react";
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
  const lastNew = useRef<number[]>([]);

  useEffect(() => {
    if (!status.length || data == null) return;

    const completed = status.filter(
      (j) => j.status === "complete" || j.status === "failed",
    );

    const newJobs = status.filter(
      (job) => data.find((e) => e.id === job.jobId) == null,
    );

    if (newJobs.length > 0) {
      for (const job of newJobs) {
        if (lastNew.current.includes(job.jobId)) {
          remove([job.jobId]);
        }
      }
    }

    if (completed.length > 0) {
      refetch().then(() => {
        remove(completed.map((j) => j.jobId));
      });
    } else if (newJobs.length > 0) {
      refetch();
      lastNew.current = newJobs.map((j) => j.jobId);
    }
  }, [status, data, refetch, remove]);
}
