import { EventSchemas, EventType } from "@/lib/events/eventSchemas";
import { atom, PrimitiveAtom } from "jotai";
import z from "zod";
import { atomFamily } from "jotai-family";
import { atomWithStorage } from "jotai/utils";
import { JOB_HISTORY_STORAGE_KEY } from "@/features/chat/constants";

type EventPayload<T extends EventType> = z.infer<(typeof EventSchemas)[T]>;

export const createLocalStorageStatusAtom = <T extends EventType>() =>
  atomWithStorage<EventPayload<T>[]>(JOB_HISTORY_STORAGE_KEY, []);

export const createStatusAtom = <T extends EventType>() =>
  atom<EventPayload<T>[]>([]);

export const createUpsertStatusAtom = <T extends EventType, K>(
  statusAtom: PrimitiveAtom<EventPayload<T>[]>,
  keyFn: (item: EventPayload<T>) => K,
) => {
  return atom(null, (_, set, update: z.infer<(typeof EventSchemas)[T]>) => {
    set(statusAtom, (prev) => [
      ...prev.filter((j) => keyFn(j) !== keyFn(update)),
      update,
    ]);
  });
};

export const createGetStatusById = <T extends EventType, K>(
  statusAtom: PrimitiveAtom<EventPayload<T>[]>,
  keyFn: (item: EventPayload<T>) => K,
) => {
  return atomFamily((id: K) =>
    atom((get) => get(statusAtom).find((j) => keyFn(j) === id)),
  );
};

export const createRemoveStatusAtom = <T extends EventType, K>(
  statusAtom: PrimitiveAtom<EventPayload<T>[]>,
  keyFn: (item: EventPayload<T>) => K,
) =>
  atom(null, (_, set, ids: K[]) => {
    set(statusAtom, (prev) => prev.filter((j) => !ids.includes(keyFn(j))));
  });

export const createClearStatusAtom = <T extends EventType>(
  statusAtom: PrimitiveAtom<EventPayload<T>[]>,
) =>
  atom(null, (_, set) => {
    set(statusAtom, []);
  });
