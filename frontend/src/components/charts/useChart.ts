import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

export const useChart = () => {
  const [dimensions, setDimensions] = useState({ width: 800, height: 800 });
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const contentRef = useRef<SVGGElement | null>(null);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry?.contentRect) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    if (!svgRef.current || !contentRef.current) return;
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 4])
      .on("zoom", (event) => {
        d3.select(contentRef.current).attr("transform", event.transform);
      });

    d3.select(svgRef.current).call(zoom);
  }, [dimensions]);

  return {
    dimensions,
    wrapperRef,
    svgRef,
    contentRef,
  };
};
