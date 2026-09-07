import { ForceGraphPoint } from "@/components/d3/ForceGraph/types";

export type CorpusExplorerPoint = ForceGraphPoint & {
  type: "topic" | "concept" | "entity";
  subvalues: Record<string, number>;
};

export type NodeTopic = {
  id: string;
  name: string;
  support: number;
  docSupport: number;
};

export type TopicNode = {
  id: string;
  name: string;
  parent: string | null;
  isLeaf: boolean;
  topics?: NodeTopic[];
  children: TopicNode[];
};
