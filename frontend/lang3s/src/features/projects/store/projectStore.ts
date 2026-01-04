import { atom } from "jotai";
import { Project } from "@/features/projects/types";
import { ParsedSearchParams } from "@/features/search/schemas";

export const currentProjectAtom = atom<Project>({
  name: "No Project",
  id: "",
  dataParams: {},
});

export const updateProjectSearchParams = atom(
  null,
  (_, set, params: ParsedSearchParams) => {
    set(currentProjectAtom, (prev) => ({ ...prev, dataParams: params }));
  },
);
