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
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, []);
  return {
    dimensions,
  };
};
