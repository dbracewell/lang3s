import { cn } from "@/lib/utils/cn";
import React, { CSSProperties, useEffect, useRef, useState } from "react";
import { select } from "d3-selection";
import * as d3 from "d3";
import type { ChartData, ChartSeries, CountType } from "@/clients/analytics";
import { selectCountValue, truncateLabel } from "@/features/reports/lib/utils";
import { formatCountTypeName } from "@/features/reports/lib/formatters";

type HeatMapProps = {
  data: ChartData[];
  className?: string;
  styles?: HeatMapStyles;
  svgStyle?: CSSProperties;
  countType: CountType;
};

export interface HeatMapStyles {
  backgroundColor?: string;
  tooltipBg?: string;
  tooltipTextColor?: string;
}

export const HeatMap = ({
  data,
  className,
  styles = {},
  countType,
  svgStyle,
}: HeatMapProps) => {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 400 });
  const svgRef = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    if (data.length == 0) return;
    if (svgRef == null) return;

    const {
      backgroundColor = "var(--color-background)",
      tooltipBg = "var(--color-background)",
      tooltipTextColor = "var(--color-foreground)",
    } = styles;

    const svg = select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous content
    const adjustedWith = dimensions.width - 20;
    const adjustedHeight = dimensions.height - 20;
    svg
      .attr("width", adjustedHeight)
      .attr("height", adjustedHeight)
      .style("background-color", backgroundColor);

    const tooltip = select(tooltipRef.current)
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", tooltipBg)
      .style("color", tooltipTextColor)
      .style("border", "2px solid var(--color-border)")
      .style("padding", "6px 10px")
      .style("border-radius", "16px")
      .style("font-size", "14px")
      .style("transition", "opacity 0.2s ease")
      .style("opacity", "0")
      .style("pointer-events", "none");

    const xGroup = [...new Set(data.map((d) => String(d.text1)))].sort();
    const yGroup = [...new Set(data.map((d) => String(d.text2)))]
      .sort()
      .reverse();
    const maxvalue = Math.max(
      ...data.map((d) =>
        d.text1 === d.text2 ? 0 : selectCountValue(d, countType),
      ),
    );
    const x = d3
      .scaleBand()
      .range([200, adjustedWith])
      .domain(xGroup)
      .padding(0.05);

    svg
      .append("g")
      .style("font-size", 14)
      .style("writing-mode", "sideways-lr")
      .style("text-anchor", "start")
      .call(
        d3
          .axisBottom(x)
          .tickSize(0)
          .tickPadding(10)
          .tickFormat((d, _) => truncateLabel(d, 12)),
      )
      .style("transform", "translateY(90px)")
      .select(".domain")
      .remove();

    const y = d3
      .scaleBand()
      .range([adjustedHeight - 20, 120])
      .domain(yGroup)
      .padding(0.05);
    svg
      .append("g")
      .style("font-size", 14)
      .style("text-anchor", "end")
      .call(
        d3
          .axisLeft(y)
          .tickSize(0)
          .tickPadding(10)
          .tickFormat((d, _) => truncateLabel(d, 20)),
      )
      .style("transform", "translateX(195px)")
      .select(".domain")
      .remove();

    const myColor = d3
      .scaleSequential()
      .domain([0, Math.log(maxvalue)])
      //@ts-ignore
      .interpolator(d3.interpolateBlues)
      .clamp(true);

    svg
      .selectAll()
      .data(data, function (d) {
        return d?.text1 + ":" + d?.text2;
      })
      .enter()
      .append("rect")
      // @ts-ignore
      .attr("x", (d) => {
        return x(String(d.text1));
      })
      // @ts-ignore
      .attr("y", (d) => {
        return y(String(d.text2));
      })
      .attr("rx", 4)
      .attr("ry", 4)
      .attr("width", x.bandwidth())
      .attr("height", y.bandwidth())
      .style("fill", function (d) {
        return myColor(Math.log(selectCountValue(d, countType)));
      })
      .style("stroke-width", 2)
      .style("stroke", "none")
      // .style("opacity", 0.8)
      .on("mouseover", function (_, d: ChartData) {
        tooltip
          .style("visibility", "visible")
          .html(
            `<p>X Axis: <b>${d.text1}</b></p><p>Y Axis: <b>${d.text2}</b></p><p>${formatCountTypeName(countType)}: <b>${selectCountValue(d, countType)}</b></p>`,
          );
        d3.select(this)
          .style("stroke", "var(--color-foreground)")
          .style("opacity", 1);
      })
      .on("mousemove", (event: { pageY: number; pageX: number }) => {
        const bounds = (
          wrapperRef.current as HTMLDivElement
        ).getBoundingClientRect();
        const yPosition = event.pageY - bounds.top + 10;
        const xPosition = event.pageX - bounds.left + 10;
        const rect = tooltip.node()?.getBoundingClientRect();
        const tooltipHeight = rect?.height ?? 118;
        const tooltipWidth = rect?.width ?? 300;
        tooltip
          .style("opacity", 1)
          .style(
            "left",
            `${xPosition >= bounds.width - tooltipWidth ? xPosition - tooltipWidth - 20 : xPosition}px`,
          )
          .style(
            "top",
            `${yPosition >= bounds.height - tooltipHeight ? yPosition - tooltipHeight - 17 : yPosition}px`,
          );
      })
      .on("mouseout", function (_: ChartSeries) {
        tooltip.style("opacity", 0).style("visibility", "hidden");
        d3.select(this).style("stroke", "none").style("opacity", 1.0);
      });
  }, [countType, data, dimensions, styles]);

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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={wrapperRef}
        id="wrapperDiv"
        className="relative h-full min-h-0 w-full flex-1 grow"
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          className={cn(
            "m-auto h-full w-full opacity-0 transition-opacity duration-300 ease-in",
            dimensions && "opacity-100",
            className,
          )}
          style={svgStyle}
          preserveAspectRatio="xMidYMid meet"
        />
        <div ref={tooltipRef} />
      </div>
    </div>
  );
};
