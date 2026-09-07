import { RefObject, useEffect, useState } from "react";

type ResizeObserverProps = {
  wrapperRef: RefObject<HTMLDivElement | null>;
};

export const useResizeObserver = ({ wrapperRef }: ResizeObserverProps) => {
  const [dimensions, setDimensions] = useState({ width: 800, height: 800 });
  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry?.contentRect) {
        const { width, height } = entry.contentRect;
        setDimensions((prev) => {
          if (
            Math.abs(prev.width - width) < 1 &&
            Math.abs(prev.height - height) < 1
          )
            return prev;
          return { width, height };
        });
      }
    });

    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, [wrapperRef]);
  return {
    dimensions,
  };
};
