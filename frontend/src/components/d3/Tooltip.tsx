import { HTMLAttributes, useEffect, useRef } from "react";
import {useD3Context} from "@/components/d3/D3ContextType";
import {cn} from "@/lib/utils/cn";

export const Tooltip = ({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) => {
  const { registerRef, hoveredNode } = useD3Context();
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (tooltipRef.current == null) return;
    if (hoveredNode == null) {
      tooltipRef.current.style.visibility = "hidden";
    } else {
      tooltipRef.current.style.visibility = "visible";
    }
  }, [hoveredNode]);

  return (
    <div
      {...props}
      className={cn("absolute", className)}
      style={{
        visibility: "hidden",
      }}
      ref={(node) => {
        tooltipRef.current = node;
        registerRef("tooltip", tooltipRef);
      }}
    >
      {children}
    </div>
  );
};