import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import { Simulation } from "d3";
import { RefObject } from "react";

export interface ForceGraphPoint extends SimulationNodeDatum {
  id: string;
  text: string;
  display: string;
  value: number;
  r?: number;
  color?: string;
}

export interface ForceGraphSimilarity<
  K extends ForceGraphPoint,
> extends SimulationLinkDatum<K> {
  id1: string;
  id2: string;
  similarity: number;
  source: K;
  target: K;
}

export type SimulatorProps<Point extends ForceGraphPoint> = {
  simulation: Simulation<Point, undefined>;
  svg: SVGSVGElement;
  nodes: Point[];
  links: ForceGraphSimilarity<Point>[];
  width: number;
  height: number;
  colliderFn?: (point: Point) => number;
  getRef: (name: string) => RefObject<any>;
  setHoveredNode: (node: Point) => void;
};

export type simulationFn<Point extends ForceGraphPoint> = (
  props: SimulatorProps<Point>,
) => void;

export type ForceGraphMouseEventProps<Point extends ForceGraphPoint> = {
  event: MouseEvent;
  point: Point;
  nodes: Point[];
  links: ForceGraphSimilarity<Point>[];
  setHoveredNode: (node: Point | null) => void;
  getRef: (name: string) => RefObject<any>;
};

export type ForceGraphMouseEvent<Point extends ForceGraphPoint> = (
  props: ForceGraphMouseEventProps<Point>,
) => boolean;
