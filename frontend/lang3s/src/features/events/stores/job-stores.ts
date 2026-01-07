import {
  createGetStatusById,
  createLocalStorageStatusAtom,
  createRemoveStatusAtom,
  createUpsertStatusAtom,
} from "@/features/events/stores/create-status-atom";

export const jobStatusAtom = createLocalStorageStatusAtom<"job:update">();

export const jobStatusByIdAtom = createGetStatusById<"job:update", number>(
  jobStatusAtom,
  (item) => item.jobId,
);

export const upsertJobStatusAtom = createUpsertStatusAtom<"job:update", number>(
  jobStatusAtom,
  (item) => item.jobId,
);

export const removeJobStatusAtom = createRemoveStatusAtom<"job:update", number>(
  jobStatusAtom,
  (item) => item.jobId,
);
