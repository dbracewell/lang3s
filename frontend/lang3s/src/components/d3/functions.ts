import { BaseType } from "d3";
import { select } from "d3-selection";

export const selectSVGElement = <E extends BaseType, R>(
  svg: SVGSVGElement,
  name: string,
) => {
  return select(svg).selectAll<E, R>(name);
};
