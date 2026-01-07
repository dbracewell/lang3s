import {
  createGetStatusById,
  createRemoveStatusAtom,
  createStatusAtom,
  createUpsertStatusAtom,
} from "@/features/events/stores/create-status-atom";

export const agentStatusAtom = createStatusAtom<"agent:update">();

export const agentStatusById = createGetStatusById<"agent:update", string>(
  agentStatusAtom,
  (item) => item.id,
);

export const upsertAgentStatus = createUpsertStatusAtom<"agent:update", string>(
  agentStatusAtom,
  (item) => item.id,
);

export const removeAgentStatus = createRemoveStatusAtom<"agent:update", string>(
  agentStatusAtom,
  (item) => item.id,
);
