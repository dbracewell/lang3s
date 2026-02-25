"use client";
import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { useResizeObserver } from "@/components/charts/useResizeObserver";

interface Node {
  id: string;
  group: string; // Used for coloring (e.g., category)
}

interface Link {
  source: string;
  target: string;
  value: number; // PMI or Similarity score
}

interface LinearChordProps {
  data: {
    nodes: Node[];
    links: Link[];
  };
  width?: number;
  height?: number;
}

const LinearChordDiagram: React.FC<LinearChordProps> = ({
  data,
  width = 1000,
  height = 600,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const { dimensions } = useResizeObserver({
    wrapperRef,
  });

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    // 1. Clear previous render
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 50, right: 30, bottom: 50, left: 30 };
    const innerWidth = dimensions.width - margin.left - margin.right;
    const innerHeight = dimensions.height - margin.top - margin.bottom;

    // 2. Setup Scales & Domains
    // Sort nodes by group to cluster similar categories together
    const sortedNodes = [...data.nodes].sort(
      (a, b) => a.group.localeCompare(b.group) || a.id.localeCompare(b.id),
    );

    const allNodeIds = sortedNodes.map((d) => d.id);

    // X scale positions nodes along the bottom
    const x = d3
      .scalePoint()
      .range([0, innerWidth])
      .domain(allNodeIds)
      .padding(0.5);

    // Color scale for groups
    const color = d3.scaleOrdinal(d3.schemeCategory10);

    // 3. Create Container Group
    // We create a specific 'g' for zooming
    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // 4. Zoom Behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 8]) // Zoom limits
      .extent([
        [0, 0],
        [width, height],
      ])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // 5. Draw Links (Arcs)
    const links = g
      .selectAll("path")
      .data(data.links)
      .join("path")
      .attr("class", "link")
      .attr("d", (d) => {
        const start = x(d.source);
        const end = x(d.target);

        if (start === undefined || end === undefined) return null;

        // Create an arc: M start,0 A rx,ry 0 0,1 end,0
        // Height of arc depends on distance between nodes
        const radius = Math.abs(end - start) / 2;

        // We flip the arc to go UP from the baseline (y = innerHeight)
        return `
          M ${start},${innerHeight} 
          A ${radius},${radius} 0 0,1 ${end},${innerHeight}
        `;
      })
      .style("fill", "none")
      .style("stroke", "#64748b") // Slate-500
      .style("stroke-width", (d) => Math.max(1, d.value))
      .style("opacity", 0.2);

    // 6. Draw Nodes (Circles)
    const nodes = g
      .selectAll("circle")
      .data(sortedNodes)
      .join("circle")
      .attr("cx", (d) => x(d.id) || 0)
      .attr("cy", innerHeight)
      .attr("r", 6)
      .style("fill", (d) => color(d.group))
      .style("stroke", "#fff")
      .style("stroke-width", 1.5)
      .style("cursor", "pointer");

    // 7. Draw Labels
    const labels = g
      .selectAll("text")
      .data(sortedNodes)
      .join("text")
      .attr("x", (d) => x(d.id) || 0)
      .attr("y", innerHeight + 20)
      .text((d) => d.id)
      .style("text-anchor", "start")
      .style("font-family", "sans-serif")
      .style("font-size", "10px")
      .style("fill", "#94a3b8") // Slate-400
      .attr("transform", (d) => {
        const xPos = x(d.id) || 0;
        const yPos = innerHeight + 20;
        return `rotate(45, ${xPos}, ${yPos})`; // Rotate labels for readability
      });

    // 8. Interactions (Hover Effects)
    nodes
      .on("mouseover", function (event, d) {
        // Highlight Node
        d3.select(this).attr("r", 10).style("stroke", "#000");

        // Highlight connected links
        links
          .style("stroke", (l) =>
            l.source === d.id || l.target === d.id ? color(d.group) : "#ddd",
          )
          .style("opacity", (l) =>
            l.source === d.id || l.target === d.id ? 1 : 0.05,
          )
          .style("stroke-width", (l) =>
            l.source === d.id || l.target === d.id ? 2 : 1,
          );

        // Tooltip
        if (tooltipRef.current) {
          tooltipRef.current.style.visibility = "visible";
          tooltipRef.current.textContent = `${d.id} (${d.group})`;
        }
      })
      .on("mousemove", (event) => {
        if (tooltipRef.current) {
          tooltipRef.current.style.top = event.pageY - 10 + "px";
          tooltipRef.current.style.left = event.pageX + 10 + "px";
        }
      })
      .on("mouseout", function () {
        // Reset everything
        d3.select(this).attr("r", 6).style("stroke", "#fff");
        links
          .style("stroke", "#64748b")
          .style("opacity", 0.2)
          .style("stroke-width", (d) => Math.max(1, d.value));

        if (tooltipRef.current) {
          tooltipRef.current.style.visibility = "hidden";
        }
      });
  }, [data, width, height, dimensions]);

  return (
    <div
      ref={wrapperRef}
      className="relative w-full overflow-hidden rounded-lg border border-gray-800 bg-gray-900"
    >
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="h-auto w-full"
        viewBox={`0 0 ${width} ${height}`}
      />
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full transform rounded bg-black px-2 py-1 text-xs text-white shadow-lg"
        style={{ visibility: "hidden" }}
      />
    </div>
  );
};

export default LinearChordDiagram;
