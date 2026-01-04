import { atom } from "jotai";
import { atomFamily } from "jotai-family";
import { EventSchemas } from "@/lib/events/eventSchemas";
import z from "zod";

type AgentStatusUpdate = z.infer<(typeof EventSchemas)["agent:update"]>;

export const agentStatusAtom = atom<AgentStatusUpdate[]>([]);

export const agentStatusById = atomFamily((id: string) =>
  atom((get) => get(agentStatusAtom).find((j) => j.id === id)),
);
export const upsertAgentStatus = atom(
  null,
  (_, set, update: AgentStatusUpdate) => {
    set(agentStatusAtom, (prev) => [
      ...prev.filter((j) => j.id !== update.id),
      update,
    ]);
  },
);

export const removeAgentStatus = atom(null, (_, set, ids: string[]) => {
  set(agentStatusAtom, (prev) => prev.filter((j) => !ids.includes(j.id)));
});
