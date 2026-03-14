import { useD3Context } from "@/components/d3/D3ContextType";
import { select } from "d3-selection";
import { cn } from "@/lib/utils/cn";
import { zoomIdentity } from "d3-zoom";
import {
  RotateCcwIcon,
  SquareSquareIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";

export const NavigationBar = ({ className }: { className?: string }) => {
  const { getRef } = useD3Context();
  const svgRef = getRef("svg");
  const zoomBehaviorRef = getRef("zoomBehavior");

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
    const width = 1000; //wrapperRef.current?.clientWidth ?? 800;
    const height = 1000; //wrapperRef.current?.clientHeight ?? 800;
    svg
      .transition()
      .duration(500)
      .call(zoomBehaviorRef.current!.translateTo as any, width / 2, height / 2);
  };

  return (
    <div
      className={cn(
        "absolute z-20 flex flex-col gap-1 rounded-md border bg-white/90 p-1 shadow-sm dark:bg-zinc-800/90",
        className,
      )}
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
  );
};
