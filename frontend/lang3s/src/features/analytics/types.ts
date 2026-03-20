import { ForceGraphPoint } from "@/components/d3/ForceGraph/types";

export type CorpusExplorerPoint = ForceGraphPoint & {
  type: "topic" | "concept" | "entity";
  subvalues: Record<string, number>;
};
