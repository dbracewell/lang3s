"use client";
import React, {
  Activity,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { useCorpusMapParams } from "@/features/analytics/hooks/useCorpusMapParams";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import { ForceGraph } from "@/components/d3/ForceGraph";
import { NavigationBar } from "@/components/d3/NavigationBar";
import {
  ForceGraphMouseEventProps,
  ForceGraphPoint,
  ForceGraphSimilarity,
  SimulatorProps,
} from "@/components/d3/ForceGraph/types";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceX,
  forceY,
} from "d3-force";
import * as d3 from "d3";
import { useTheme } from "next-themes";
import { select } from "d3-selection";
import {
  BinocularsIcon,
  ChartNoAxesGanttIcon,
  FileIcon,
  MessageSquareIcon,
  SearchIcon,
  XIcon,
} from "lucide-react";
import { capitalize, formatURL } from "@/lib/utils/formatters";
import { Hint } from "@/components/hint";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  getLinkElement,
  getNodeElement,
  getTextElement,
} from "@/components/d3/ForceGraph/functions";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { TopicCloudPoint } from "@/features/analytics/ui/components/TopicCloud";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { TopicsList } from "@/features/analytics/ui/components/TopicsList";
import { CorpusMapTabs } from "@/features/analytics/ui/components/CorpusMapTabs";
import { selectSVGElement } from "@/components/d3/functions";
import {
  GetTypeBoundsProps,
  OnInitializationProps,
} from "@/components/d3/types";
import { D3ContextProvider, useD3Context } from "@/components/d3/D3ContextType";
import { Tooltip } from "@/components/d3/Tooltip";
import {
  useFindMultiTypeMinMaxValue,
  useMultiTypeLinearScaler,
} from "@/components/d3/hooks";

const simulator = ({
  simulation,
  nodes,
  links,
  width,
  height,
  colliderFn,
  svg,
  getRef,
  setHoveredNode,
}: SimulatorProps<CustomPoint>) => {
  const conceptHullPath = selectSVGElement(svg, ".concept-path");
  const linkElement = getLinkElement(svg);
  const nodeElement = getNodeElement(svg);
  const textElement = getTextElement(svg);
  const zoomBehavior = getRef("zoomBehavior").current;
  const searchTerm = getRef("searchTerm").current ?? "";

  simulation
    .force("x", forceX<CustomPoint>(() => width / 2).strength(0.08))
    .force("y", forceY<CustomPoint>(() => height / 2).strength(0.08))
    .force(
      "link",
      forceLink<CustomPoint, ForceGraphSimilarity<CustomPoint>>(links)
        .id((d) => d.id)
        .distance((d) => Math.max(10, (1 - d.similarity) * 100))
        .strength(0.25),
    )
    .force("charge", forceManyBody().strength(-40))
    .force(
      "collide",
      forceCollide<CustomPoint>()
        .radius((d) => (colliderFn ? colliderFn(d) : (d.r ?? 10) * 200))
        .iterations(1),
    );

  const hullLine = d3.line().curve(d3.curveCatmullRomClosed);

  simulation
    .on("tick", () => {
      linkElement
        .attr("x1", (d) => d.source.x ?? 0)
        .attr("y1", (d) => d.source.y ?? 0)
        .attr("x2", (d) => d.target.x ?? 0)
        .attr("y2", (d) => d.target.y ?? 0);
      nodeElement.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      textElement.attr("transform", (d) => `translate(${d.x},${d.y})`);

      const conceptNodes = nodes.filter(
        (d) => d.type === "concept" && d.x !== undefined && d.y !== undefined,
      );

      if (conceptNodes.length >= 3) {
        const points: [number, number][] = conceptNodes.map((d) => [
          d.x! + 20,
          d.y! + 20,
        ]);
        const hull = d3.polygonHull(points);
        if (hull) conceptHullPath.attr("d", hullLine(hull));
      } else {
        conceptHullPath.attr("d", null);
      }
    })
    .on("end", () => {
      let toFocus: CustomPoint | undefined;
      let toFocusValue = 0;
      let foundMatch = false;

      nodes.forEach((node) => {
        if (searchTerm === node.text.toLowerCase()) {
          toFocus = node;
          foundMatch = true;
          toFocusValue = 10000000;
        } else if (
          !foundMatch &&
          node.type === "concept" &&
          (toFocus == null ||
            toFocus.type === "topic" ||
            node.value > toFocusValue)
        ) {
          toFocusValue = node.value;
          toFocus = node;
        } else if (
          !foundMatch &&
          node.type === "topic" &&
          (toFocus == null ||
            (toFocus.type === "topic" && node.value > toFocusValue))
        ) {
          toFocusValue = node.value;
          toFocus = node;
        }
      });
      if (toFocus == null) return;

      const targetX = toFocus.x ?? 0;
      const targetY = toFocus.y ?? 0;
      const transform = d3.zoomIdentity
        .translate((width - 20) / 2, (height - 20) / 2)
        .scale(0.7)
        .translate(-targetX + 40, -targetY - 40);

      select(svg)
        .transition()
        .duration(750)
        .call(zoomBehavior.transform as any, transform)
        .on("end", () => setHoveredNode(toFocus!));
    });
};

interface CustomPoint extends ForceGraphPoint {
  type: "topic" | "concept" | "entity";
  subvalues: Record<string, number>;
}

const getType = (point: CustomPoint) => point.type;

const getValue = (point: CustomPoint) => point.value;

const graphInitializer = ({ g, getRef }: OnInitializationProps) => {
  const hullGroup = g.append("g");
  hullGroup.append("path").attr("class", "concept-path");
  const tooltip = getRef("tooltip").current;
  const searchTerm = getRef("searchTerm").current;
  if (!!searchTerm) {
    select(tooltip).style("visibility", "visible");
  }
};

const onMouseOut = ({
  getRef,
  setHoveredNode,
}: ForceGraphMouseEventProps<CustomPoint>) => {
  const tooltip = getRef("tooltip");
  const hideTimeoutRef = getRef("hideTimeout");
  const searchTerm = getRef("searchTerm").current;

  if (!!searchTerm) {
    return false;
  }

  if (hideTimeoutRef != null) {
    hideTimeoutRef.current = setTimeout(() => {
      hideActionMenu({ setHoveredNode, tooltip: tooltip?.current });
    }, 300);
  }

  return false;
};

const onMouseEnter = ({
  event,
  getRef,
}: ForceGraphMouseEventProps<CustomPoint>) => {
  const tooltip = getRef("tooltip");
  const wrapperRef = getRef("wrapper");
  const searchTerm = getRef("searchTerm").current;

  const hideTimeoutRef = getRef("hideTimeout");
  if (hideTimeoutRef != null && hideTimeoutRef.current != null) {
    clearTimeout(hideTimeoutRef.current);
  }

  if (!!searchTerm) {
    return false;
  }

  if (
    tooltip != null &&
    tooltip.current != null &&
    wrapperRef != null &&
    wrapperRef.current != null
  ) {
    const bounds = (
      wrapperRef.current as HTMLDivElement
    ).getBoundingClientRect();
    const cursorX = event.clientX - bounds.left;
    const cursorY = event.clientY - bounds.top;

    let left = cursorX + 20;
    let top = cursorY + 20;

    select(tooltip.current)
      .style("visibility", "visible")
      .style("opacity", 1)
      .style("left", `${left}px`)
      .style("top", `${top}px`)
      .transition("transform 0.3s ease-in-out;");
  }
  return true;
};

const hideActionMenu = ({
  setHoveredNode,
  tooltip,
}: {
  setHoveredNode: (node: CustomPoint | null) => void;
  tooltip: HTMLDivElement;
}) => {
  setHoveredNode(null);
  tooltip.style.visibility = "hidden";
};

export const CorpusMap = () => {
  const [params, setParams] = useCorpusMapParams();
  const { theme } = useTheme();
  const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { data } = useTRPCQuery((trpc) =>
    trpc.analytics.getCorpusMap.queryOptions(),
  );

  const externalRefs = useMemo(
    () => ({
      hideTimeout: hideTimeoutRef,
    }),
    [],
  );

  const [selectedTopic, nodes, links] = useMemo(() => {
    if (!data) return [null, [], []];
    let selectedTopic: CustomPoint | undefined = data.nodes.find(
      (node) => node.type === "topic" && node.id === params.topicId.trim(),
    );

    if (selectedTopic == null) {
      return [
        null,
        data.nodes.filter((node) => node.type === "topic"),
        data.similarities,
      ];
    }

    const selectedConcepts = new Set(
      Object.entries(selectedTopic.subvalues)
        .filter(([_, v]) => v > 5)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 50)
        .map((n) => n[0]),
    );

    const filteredNodes = data.nodes
      .filter((node) => {
        if (selectedTopic.id === node.id && node.type === "topic") {
          return false;
        } else if (node.type === "topic") {
          return true;
        }
        return selectedConcepts.has(node.id);
      })
      .map((node) => {
        if (node.type === "topic") {
          return node;
        }
        return {
          ...node,
          value: selectedTopic.subvalues[node.id],
        };
      });

    return [selectedTopic, filteredNodes, data.similarities];
  }, [data, params.topicId]);

  const valueRanges = useFindMultiTypeMinMaxValue({
    points: data?.nodes,
    getType,
    getValue,
  });

  const getTypeFontRange = useCallback(({ bound }: GetTypeBoundsProps) => {
    return bound === "min" ? 24 : 100;
  }, []);

  const fontScales = useMultiTypeLinearScaler({
    valueRanges,
    getTypeBounds: getTypeFontRange,
  });

  const nodeScaler = useCallback(
    (point: CustomPoint) =>
      fontScales ? fontScales[point.type](point.value) * 1.5 : 10,
    [fontScales],
  );

  const fontScaler = useCallback(
    (point: CustomPoint) =>
      fontScales ? fontScales[point.type](point.value) : 10,
    [fontScales],
  );

  const colliderFn = useCallback(
    (point: CustomPoint) =>
      fontScales ? fontScales[point.type](point.value) * 4 : 10,
    [fontScales],
  );

  const colorScales = useMemo(() => {
    if (!valueRanges) return null;
    return {
      topic: d3
        .scaleSequential((t) => d3.interpolateBlues(0.2 + t * 0.7))
        .domain([
          theme === "dark" ? valueRanges.topic.max : valueRanges.topic.min,
          theme === "dark" ? valueRanges.topic.min : valueRanges.topic.max,
        ]),
      concept: d3
        .scaleSequential((t) => d3.interpolateGreens(0.2 + t * 0.6))
        .domain([
          theme === "dark" ? valueRanges.concept.max : valueRanges.concept.min,
          theme === "dark" ? valueRanges.concept.min : valueRanges.concept.max,
        ]),
    };
  }, [valueRanges, theme]);

  const styleFn = useCallback(
    (svg: SVGSVGElement) => {
      selectSVGElement(svg, ".concept-path")
        .style("fill", () =>
          theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(100,100,100,0.1)",
        )
        .style("opacity", 0.5);
      getTextElement<CustomPoint>(svg).attr("fill", (point) =>
        colorScales
          ? colorScales[point.type as "topic" | "concept"](point.value)
          : "dodger-blue-500",
      );
    },
    [colorScales, theme],
  );

  const onMouseClick = useCallback(
    ({ point }: ForceGraphMouseEventProps<CustomPoint>) => {
      if (point.type === "topic") {
        setParams({
          topicId: point.id,
          search: "",
          conceptId: "",
        });
      }
      return false;
    },
    [setParams],
  );

  if (data == null) {
    return <Spinner />;
  }

  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Corpus Explorer</h1>
      </ScrollableBox.Header>
      <div className="flex max-h-full min-h-0 flex-1 flex-col gap-4">
        <CorpusMapTabs />
        <Activity mode={params.tab === "chart" ? "visible" : "hidden"}>
          <D3ContextProvider externalRefs={externalRefs}>
            <Filter points={nodes} />
            <ForceGraph
              points={nodes}
              similarities={links}
              svgClassName="rounded-lg"
              nodeClassName="fill-transparent cursor-pointer"
              textClassName="pointer-events-none"
              fontScaler={fontScaler}
              nodeScaler={nodeScaler}
              colliderFn={colliderFn}
              styleFn={styleFn}
              onMouseEnter={onMouseEnter}
              onMouseOut={onMouseOut}
              onMouseClick={onMouseClick}
              onInitialize={graphInitializer}
              simulator={simulator}
            >
              <NavigationBar className="top-2.5 right-2.5" />
              <TopicDetails selectedTopic={selectedTopic} />
              <ToolTipContent />
            </ForceGraph>
          </D3ContextProvider>
        </Activity>
        <Activity mode={params.tab === "list" ? "visible" : "hidden"}>
          <TopicsList points={data.nodes.filter((a) => a.type === "topic")} />
        </Activity>
      </div>
    </ScrollableBox.Container>
  );
};

export const ToolTipContent = () => {
  const { hoveredNode, setHoveredNode, getRef } = useD3Context<CustomPoint>();

  useEffect(() => {
    const tooltip = getRef("tooltip").current;
    const wrapper = getRef("wrapper").current;
    const svg = getRef("svg").current;

    if (hoveredNode == null || tooltip == null || wrapper == null) return;

    const bounds = (wrapper as HTMLDivElement).getBoundingClientRect();
    const transform = d3.zoomTransform(svg);

    const [screenX, screenY] = transform.apply([
      hoveredNode.x ?? 0,
      hoveredNode.y ?? 0,
    ]);

    const actionBounds = (tooltip as HTMLDivElement).getBoundingClientRect();
    let actionHeight = actionBounds.height || 100;
    const actionWidth = actionBounds.width || 200;

    let left = screenX + 20;
    let top = screenY + 20;

    if (left + actionWidth > bounds.width) {
      left = screenX - actionWidth - 20; // Flip to the left side
    }

    if (top + actionHeight > bounds.height) {
      top = screenY - actionHeight - 20; // Flip above the node
    }

    if (left < 0) left = 10;
    if (top < 0) top = 10;

    select(tooltip)
      .style("visibility", "visible")
      .style("opacity", 1)
      .style("left", `${left}px`)
      .style("top", `${top}px`)
      .transition("transform 0.3s ease-in-out;");
  }, [hoveredNode]);

  return (
    <Tooltip
      className="bg-card/80 absolute flex max-h-70 w-70 flex-col gap-2 overflow-hidden rounded-lg border p-2 shadow-sm backdrop-blur-md"
      onMouseLeave={(e) =>
        hideActionMenu({ setHoveredNode, tooltip: e.target as HTMLDivElement })
      }
      onMouseEnter={() => {
        const timeoutRef = getRef("hideTimeout");
        if (timeoutRef != null && timeoutRef.current != null) {
          clearTimeout(timeoutRef.current);
        }
      }}
      style={{
        transition: "opacity 0.2s ease",
        opacity: 0,
      }}
    >
      {hoveredNode != null && (
        <>
          <div className="h-fit border-b pb-2 text-center text-sm font-bold text-wrap">
            {hoveredNode.text}
          </div>
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <h3 className="text-muted-foreground flex items-center gap-2 text-xs">
                {hoveredNode.type === "topic" ? (
                  <ChartNoAxesGanttIcon className="size-3" />
                ) : (
                  <MessageSquareIcon className="size-3" />
                )}
                {capitalize(hoveredNode.type)}
              </h3>
              <h3 className="text-muted-foreground flex items-center gap-2 text-xs">
                <FileIcon className="size-3" />
                <div>{hoveredNode?.value} Documents</div>
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <Hint hint="Search for related information">
                <Link
                  href={formatURL("/search", {
                    tid:
                      hoveredNode.type === "topic" ? hoveredNode.id : undefined,
                    cid:
                      hoveredNode.type === "concept"
                        ? hoveredNode.id
                        : undefined,
                    placeholder: `${capitalize(hoveredNode.type)}: ${hoveredNode.text}`,
                  })}
                  className={buttonVariants({
                    variant: "listButton",
                    size: "icon-sm",
                  })}
                >
                  <SearchIcon />
                </Link>
              </Hint>
              <Hint hint={`View ${capitalize(hoveredNode.type)} information`}>
                <Link
                  href={formatURL("/search", {
                    tid:
                      hoveredNode.type === "topic" ? hoveredNode.id : undefined,
                    cid:
                      hoveredNode.type === "concept"
                        ? hoveredNode.id
                        : undefined,
                    placeholder: `${capitalize(hoveredNode.type)}: ${hoveredNode.text}`,
                  })}
                  className={buttonVariants({
                    variant: "listButton",
                    size: "icon-sm",
                  })}
                >
                  <BinocularsIcon />
                </Link>
              </Hint>
            </div>
          </div>
          <div className="flex min-h-0 flex-col gap-2">
            <div className="border-y py-1 text-sm font-medium">
              {hoveredNode.type === "topic" ? "Concepts" : "Instances"}
            </div>
            <div className="scrollable flex flex-1 flex-col gap-1 text-xs">
              {hoveredNode && !hoveredNode.subvalues.length && (
                <div className="flex flex-1 flex-col items-center justify-center">
                  <div>No items</div>
                </div>
              )}
              {hoveredNode &&
                Object.keys(hoveredNode.subvalues).map((kw) => (
                  <div key={kw}>{kw}</div>
                ))}
            </div>
          </div>
        </>
      )}
    </Tooltip>
  );
};

export const TopicDetails = ({
  selectedTopic,
}: {
  selectedTopic: CustomPoint | null;
}) => {
  const [params, setParams] = useCorpusMapParams();
  if (selectedTopic == null) {
    return null;
  }

  return (
    <div className="bg-card/20 absolute top-2 bottom-2 left-2 z-10 flex w-80 flex-1 flex-col overflow-hidden rounded-lg border backdrop-blur-md">
      <h2 className="bg-heading mb-2 flex items-center justify-between p-1 px-2 font-bold text-white">
        <span>Topic</span>
        <Button
          variant="destructiveGhost"
          size="icon-xs"
          className="ml-2"
          onClick={() =>
            setParams({
              topicId: "",
              conceptId: "",
            })
          }
        >
          <XIcon />
        </Button>
      </h2>
      <div className="px-2 py-1 font-bold text-wrap">{selectedTopic.text}</div>
      <div className="text-muted-foreground flex items-center justify-between px-2 py-1 pb-2 text-sm">
        <div className="flex items-center gap-2">
          <Hint hint="Search for related information">
            <Link
              href={formatURL("/search", {
                tid: params.topicId,
                placeholder: `Topic ${selectedTopic.text}`,
              })}
              className={buttonVariants({
                variant: "listButton",
                size: "icon-sm",
              })}
            >
              <SearchIcon />
            </Link>
          </Hint>
          <Hint hint={"View topic information"}>
            <Link
              href={formatURL("/search", {
                tid: params.topicId,
                placeholder: `Topic ${selectedTopic.text}`,
              })}
              className={buttonVariants({
                variant: "listButton",
                size: "icon-sm",
              })}
            >
              <BinocularsIcon />
            </Link>
          </Hint>
        </div>
        <div>{selectedTopic.value} Documents</div>
      </div>
      <h2 className="bg-heading mb-2 p-1 px-2 font-bold text-white">
        Concepts
      </h2>
      <div className="scrollable flex flex-1 flex-col gap-0.5 pb-5">
        {selectedTopic.subvalues.length === 0 && (
          <div className="flex flex-1 items-center justify-center text-lg font-bold">
            No Concepts
          </div>
        )}
        {Object.entries(selectedTopic.subvalues)
          .filter(([_, v]) => v > 5)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 50)
          .map((n) => (
            <div
              onClick={() =>
                setParams({
                  search: n[0],
                })
              }
              className="text-foreground hover:text-dodger-blue-500 cursor-pointer px-2 hover:underline"
              key={n[0]}
            >
              {n[0]}
            </div>
          ))}
      </div>
    </div>
  );
};

const Filter = ({ points }: { points: CustomPoint[] }) => {
  const [params, setParams] = useCorpusMapParams();
  const { getRef, setHoveredNode, registerRef } = useD3Context<CustomPoint>();
  const searchTermRef = useRef<string>("");
  registerRef("searchTerm", searchTermRef);

  useEffect(() => {
    const svg = getRef("svg").current as SVGSVGElement;
    const wrapper = getRef("wrapper").current;
    const zoomBehaviorRef = getRef("zoomBehavior");
    const tooltip = getRef("tooltip").current;

    if (svg == null || wrapper == null) return;

    const searchTerm = params.search.trim().toLowerCase();
    searchTermRef.current = searchTerm;

    const toHighlight = new Set(
      points
        .filter((p) => !searchTerm || p.text.toLowerCase().includes(searchTerm))
        .map((p) => p.id),
    );

    let bestMatch: CustomPoint | null = null;
    getTextElement<CustomPoint>(svg)
      .attr("stroke-opacity", (d) => (searchTerm === d.id ? 1 : 0))
      .style("transition", "opacity 0.2s ease, filter 0.2s ease")
      .style("opacity", (d) => {
        if (!searchTerm) return 1;

        const target = d.text;
        const isMatch = target.toLowerCase() === searchTerm;

        if (isMatch) {
          bestMatch = d;
        }

        return isMatch || toHighlight.has(d.id) ? 1 : 0.2;
      })
      .style("filter", (d) => {
        if (!searchTerm) return "none";
        return toHighlight.has(d.id) ? "none" : "grayscale(50%)";
      });

    if (searchTerm && bestMatch) {
      setHoveredNode(bestMatch);
      // Extract the coordinates (fallback to 0)
      const targetX = (bestMatch as TopicCloudPoint).x ?? 0;
      const targetY = (bestMatch as TopicCloudPoint).y ?? 0;

      // Use the same coordinate space size as your physics engine
      const { width, height } = (
        wrapper as HTMLDivElement
      ).getBoundingClientRect();

      // Calculate the transform: Move to center, apply scale, reverse by target coordinates
      const transform = d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(0.7)
        .translate(-targetX, -targetY);

      select(svg)
        .transition()
        .duration(750)
        .call(zoomBehaviorRef.current!.transform as any, transform)
        .on("start", () => select(tooltip).style("visibility", "hidden"))
        .on("end", () => {
          select(tooltip)
            .style("visibility", "visible")
            .style("opacity", 1)
            .style("left", "calc(50% + 30px)")
            .style("top", "calc(50% + 20px)");
        });
    } else {
      setHoveredNode(null);
    }
  }, [getRef, points, params.search, setHoveredNode]);

  return (
    <InputGroup className="max-w-md">
      <InputGroupInput
        placeholder="Search for Topics/Concepts..."
        value={params.search ?? ""}
        onChange={(e) => setParams({ search: e.target.value })}
      />
      <InputGroupAddon align="inline-start">
        <SearchIcon />
      </InputGroupAddon>
      {!!params.search.trim() && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            variant="destructiveGhost"
            className="border-0!"
            size="icon-xs"
            type="button"
            onClick={() => {
              setParams({ search: "" });
            }}
          >
            <XIcon />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
};
