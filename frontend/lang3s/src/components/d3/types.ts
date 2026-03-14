import { RefObject } from "react";
import { Selection } from "d3";

export type RegisterRefFn = (name: string, node: RefObject<any>) => void;
export type GetRefFn = (name: string) => RefObject<any | null>;

export type RefContextType = {
  registerRef: RegisterRefFn;
  getRef: GetRefFn;
};

export type OnInitializationProps = {
  getRef: (name: string) => RefObject<any>;
  g: Selection<SVGGElement, unknown, null, undefined>;
};

export type OnInitializeFn = (props: OnInitializationProps) => void;

export type SVGStyleFn = (svg: SVGSVGElement) => void;

export type GetTypeBoundsProps = {
  type: string;
  bound: "min" | "max";
};

export type getTypeBoundsFn = ({ type, bound }: GetTypeBoundsProps) => number;
