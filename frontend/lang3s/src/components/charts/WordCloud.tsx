import React, { memo, useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import cloud from "d3-cloud";
import {
  Loader2,
  RotateCcwIcon,
  SearchIcon,
  SquareSquareIcon,
  XIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import { useResizeObserver } from "@/components/charts/useResizeObserver";
import { select } from "d3-selection";
import { type ZoomBehavior, zoomIdentity } from "d3-zoom";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";

export type NodeType = "topic" | "concept" | "entity";

export interface CloudWord {
  id: string | number;
  text: string;
  value: number; // Represents 'support' or frequency
  type: NodeType;
}

// d3-cloud extends our word objects with positioning data during the layout phase
export interface LayoutWord extends Omit<cloud.Word, "text">, CloudWord {
  originalText: string;
}

interface CorpusWordCloudProps {
  data: CloudWord[];
  onWordClick: (word: CloudWord) => void;
}

const truncateText = (text: string, maxLength = 35) => {
  if (text.length <= maxLength) return text;
  // Try to cut cleanly at a space so we don't slice words in half
  const truncated = text.substring(0, text.lastIndexOf(" ", maxLength));
  return `${truncated || text.substring(0, maxLength)}...`;
};

const CorpusWordCloud: React.FC<CorpusWordCloudProps> = ({
  data,
  onWordClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(true);
  const { dimensions } = useResizeObserver({ wrapperRef });
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(
    null,
  );
  const [searchTerm, setSearchTerm] = useState("");
  const searchTermRef = useRef("");

  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    x: number;
    y: number;
    text: string;
    value: string;
  } | null>(null);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
    searchTermRef.current = e.target.value;
  };

  const resetSearch = () => {
    setSearchTerm("");
    searchTermRef.current = "";
  };

  useEffect(() => {
    if (data == null || !data.length || !svgRef.current || !wrapperRef.current)
      return;

    setIsDrawing(true);

    const viewportWidth = wrapperRef.current.clientWidth;
    const viewportHeight = wrapperRef.current.clientHeight; // Adjust for search bar
    const virtualDimension = Math.max(2000, data.length * 25);

    const svg = d3.select<SVGSVGElement, unknown>(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous renders

    const maxValues = data.reduce(
      (agg, d) => {
        if (d.value > agg[d.type]) {
          agg[d.type] = d.value;
        }
        return agg;
      },
      { topic: 0, concept: 0, entity: 0 },
    );

    const topicFontSizes = d3.scaleLinear(
      [1, maxValues["topic"] + 1],
      [24, 100],
    );
    const conceptFontSizes = d3.scaleLinear(
      [1, maxValues["concept"] + 1],
      [24, 100],
    );

    const topicColor = d3
      .scaleSequential((t) => d3.interpolateBlues(0.2 + t * 0.7))
      .domain([maxValues["topic"] + 1, 1]);

    const conceptColor = d3
      .scaleSequential((t) => d3.interpolateRdBu(0.2 + t * 0.6))
      .domain([maxValues["concept"] + 1, 1]);

    const entityColor = d3
      .scaleSequential((t) => d3.interpolatePurples(0.4 + t * 0.6))
      .domain([1, data[0].value + 1]);

    const layoutWords: LayoutWord[] = data.map((d) => ({
      ...d,
      originalText: d.text,
      text: truncateText(d.text, 35),
    }));

    // Setup the D3 Cloud layout
    const layout = cloud<LayoutWord>()
      .size([virtualDimension, virtualDimension])
      .words(layoutWords) // Clone data to prevent mutating props
      .padding(6) // Space between words
      .rotate(() => 0)
      .font("Inter, sans-serif")
      .fontSize((d) => {
        if (d.type === "topic") {
          return topicFontSizes(d.value);
        }
        return conceptFontSizes(d.value);
      })
      .on("end", draw);

    layout.start();

    // The draw function called when the layout algorithm finishes
    function draw(words: LayoutWord[]) {
      // Setup the Zoom Behavior
      const zoomBehavior = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 5]) // 0.1 allows the user to zoom way out to see the whole macro-structure
        .on("zoom", (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
          zoomGroup.attr("transform", event.transform.toString());
        });

      svg
        .attr("width", viewportWidth)
        .attr("height", viewportHeight)
        .call(zoomBehavior);

      const zoomGroup = svg.append("g");

      // The inner group handles centering the d3-cloud layout
      const centerGroup = zoomGroup
        .append("g")
        .attr(
          "transform",
          `translate(${viewportWidth / 2},${viewportHeight / 2})`,
        );

      centerGroup
        .selectAll("text")
        .data(words)
        .enter()
        .append("text")
        .attr("class", "word-node cursor-pointer")
        .style("font-size", (d) => {
          return `${d.size}px`;
        })
        .style("font-family", "Inter, sans-serif")
        .style("font-weight", "600")
        .style("fill", (d) => {
          if (d.type === "topic") return topicColor(d.value);
          if (d.type === "concept") return conceptColor(d.value);
          if (d.type === "entity") return entityColor(d.value);

          return "hsl(var(--muted-foreground))"; // Fallback
        })
        .attr("text-anchor", "middle")
        .attr(
          "transform",
          (d) => `translate(${d.x},${d.y}) rotate(${d.rotate})`,
        )
        .text((d) => d.text)
        .on("mousemove", (event: MouseEvent, d: LayoutWord) => {
          // Update tooltip position to follow the mouse slightly offset
          let valueType = "Sentences";
          if (d.type === "concept") {
            valueType = "Documents";
          }
          setTooltip({
            visible: true,
            x: event.clientX + 15,
            y: event.clientY + 15,
            text: d.originalText,
            value: `${d.value} ${valueType}`,
          });
        })
        .on("click", (_event, d) => {
          setTooltip(null);
          onWordClick(d as CloudWord);
        })
        .on("mouseenter", (event: MouseEvent, d: LayoutWord) => {
          if (searchTermRef.current.trim() !== "") return;

          const target = event.currentTarget as SVGTextElement;
          // Select ALL text elements within the parent group and dim them
          d3.select(target.parentNode as Element)
            .selectAll("text")
            .style("opacity", 0.4)
            .style("filter", "grayscale(50%)"); // Optional: mutes the colors of background words

          // Re-select the hovered element to override the dimming
          d3.select(target)
            .style("opacity", 1)
            .style("filter", "none")
            .style("stroke", () => {
              // Add a subtle outline matching its type to make it pop
              if (d.type === "topic") return topicColor(d.value);
              if (d.type === "concept") return conceptColor(d.value);
              if (d.type === "entity") return entityColor(d.value);
              return "currentColor";
            })
            .style("stroke-width", "1px");
        })
        .on("mouseleave", (event: MouseEvent) => {
          setTooltip(null);
          if (searchTermRef.current.trim() !== "") return;

          const target = event.currentTarget as SVGTextElement;

          // Restore all text elements in the group to their default state
          d3.select(target.parentNode as Element)
            .selectAll("text")
            .style("opacity", 1)
            .style("filter", "none")
            .style("stroke", "none");
        });

      const topWord = words.reduce((prev, current) =>
        prev.value > current.value ? prev : current,
      );

      // 2. Extract its calculated coordinates (fallback to 0)
      const targetX = topWord.x ?? 0;
      const targetY = topWord.y ?? 0;

      const initialScale = 0.5;

      const initialTransform = d3.zoomIdentity
        .translate(viewportWidth / 2, viewportHeight / 2)
        .scale(initialScale)
        .translate(
          -(viewportWidth / 2 + targetX),
          -(viewportHeight / 2 + targetY),
        );
      svg.call(zoomBehavior.transform, initialTransform);

      zoomBehaviorRef.current = zoomBehavior;
      setIsDrawing(false);
    }
  }, [data, onWordClick]);

  useEffect(() => {
    if (isDrawing || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const textNodes = svg.selectAll<SVGTextElement, LayoutWord>(".word-node");
    const term = searchTerm.trim().toLowerCase();

    if (!term) {
      // If search is empty, reset everything to normal
      textNodes
        .style("opacity", 1)
        .style("filter", "none")
        .style("stroke", "none");
      return;
    }

    // Apply highlighting based on substring match
    textNodes.each(function (d) {
      const isMatch = d.text.toLowerCase().includes(term);
      const node = d3.select(this);

      if (isMatch) {
        node
          .style("opacity", 1)
          .style("filter", "none")
          .style("stroke", "var(--dodger-blue-200)")
          .style("stroke-width", "1px")
          .style("scale", 1.5);
      } else {
        node
          .style("opacity", 0.2)
          .style("filter", "grayscale(50%)")
          .style("stroke", "none")
          .style("scale", 1.0);
      }
    });
  }, [searchTerm, isDrawing]);

  const handleZoomIn = () => {
    const svg = select(svgRef.current);
    const t = svg.transition().duration(250);
    zoomBehaviorRef.current?.scaleBy(t as any, 1.2);
  };

  const handleZoomOut = () => {
    const svg = select(svgRef.current);
    zoomBehaviorRef.current?.scaleBy(
      svg.transition().duration(250) as any,
      0.8,
    );
  };

  const handleResetZoom = () => {
    const svg = select(svgRef.current);
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current?.transform as any, zoomIdentity);
  };

  const handleRecenter = () => {
    const svg = select(svgRef.current);
    const { width, height } = dimensions;
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current!.translateTo as any, width / 2, height / 2);
  };

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col gap-6">
      <Filter
        filter={searchTerm}
        setFilter={handleSearchChange}
        resetFilter={resetSearch}
      />
      <div className="relative w-full flex-1 overflow-hidden">
        <div
          className="bg-white/90 dark:bg-zinc-800/90"
          style={{
            position: "absolute",
            top: "10px",
            right: "15px",
            borderRadius: "8px",
            padding: "4px",
            boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          <button
            onClick={handleZoomIn}
            className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
          >
            <ZoomInIcon className="size-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
          >
            <ZoomOutIcon className="size-4" />
          </button>
          <button
            onClick={handleResetZoom}
            className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
          >
            <RotateCcwIcon className="size-4" />
          </button>
          <button
            onClick={handleRecenter}
            className="p-2 hover:bg-slate-100 dark:hover:bg-zinc-700"
          >
            <SquareSquareIcon className="size-4" />
          </button>
        </div>
        {isDrawing && (
          <div className="bg-background/50 absolute inset-0 z-50 flex items-center justify-center">
            <Loader2 className="text-primary h-8 w-8 animate-spin" />
          </div>
        )}
        <div ref={wrapperRef} className="flex h-full min-h-0 flex-1 flex-col">
          <svg
            ref={svgRef}
            className="h-full w-full cursor-grab active:cursor-grabbing"
          />
        </div>
        {tooltip && tooltip.visible && (
          <div
            className="fixed z-100 max-w-sm rounded-lg border border-slate-900 bg-slate-700 p-3 px-3 py-2 text-center text-sm whitespace-pre-line text-white"
            style={{
              left: tooltip.x,
              top: tooltip.y,
            }}
          >
            {tooltip.text} ({tooltip.value})
          </div>
        )}
      </div>
    </div>
  );
};

const Filter = ({
  filter,
  setFilter,
  resetFilter,
}: {
  filter: string;
  setFilter: (e: React.ChangeEvent<HTMLInputElement>) => void;
  resetFilter: () => void;
}) => {
  return (
    <InputGroup className="max-w-md">
      <InputGroupInput
        placeholder="Search..."
        value={filter ?? ""}
        onChange={setFilter}
      />
      <InputGroupAddon align="inline-start">
        <SearchIcon className="h-5 w-5" />
      </InputGroupAddon>
      {!!filter.trim() && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            variant="destructiveGhost"
            className="border-0!"
            size="icon-xs"
            type="button"
            onClick={() => {
              resetFilter();
            }}
          >
            <XIcon />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
};

export default memo(CorpusWordCloud);
