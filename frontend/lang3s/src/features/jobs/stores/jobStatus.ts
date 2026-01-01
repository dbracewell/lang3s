import { atom } from "jotai";
import { atomFamily } from "jotai-family";
import { JobStatusUpdateType } from "@/lib/events/eventSchemas";

export const jobStatusAtom = atom<JobStatusUpdateType[]>([]);

export const jobStatusByIdAtom = atomFamily((jobId: number) =>
  atom((get) => get(jobStatusAtom).find((j) => j.jobId === jobId)),
);
export const upsertJobStatusAtom = atom(
  null,
  (_, set, job: JobStatusUpdateType) => {
    set(jobStatusAtom, (prev) => [
      ...prev.filter((j) => j.jobId !== job.jobId),
      job,
    ]);
  },
);

export const removeJobStatusAtom = atom(null, (_, set, ids: number[]) => {
  set(jobStatusAtom, (prev) => prev.filter((j) => !ids.includes(j.jobId)));
});
