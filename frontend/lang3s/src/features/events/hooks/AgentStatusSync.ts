"use client";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";
import {
  agentStatusAtom,
  removeAgentStatus,
} from "@/features/events/stores/chat-stores";

export function useAgentStatusSync(
  data: { id: string }[] | undefined,
  refetch: () => Promise<any>,
) {
  const status = useAtomValue(agentStatusAtom);
  const remove = useSetAtom(removeAgentStatus);

  useEffect(() => {
    if (!status.length || data == null) return;

    const completed = status.filter((j) => j.progress === 100);

    const newUpdates = status.filter(
      (job) => !data?.find((e) => e.id === job.id),
    );

    if (completed.length) {
      refetch().then(() => {
        remove(completed.map((j) => j.id));
      });
    } else if (newUpdates.length) {
      refetch();
    }
  }, [status, data, refetch, remove]);
}
