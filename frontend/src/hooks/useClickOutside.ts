import React, { useEffect } from "react";

export const useClickOutside = (
  ref: React.RefObject<HTMLElement | null>[],
  handler: () => void,
) => {
  useEffect(() => {
    const listener = (event: MouseEvent | TouchEvent) => {
      const ele = event.target as HTMLElement;
      if (
        ele.parentElement == null ||
        ref.some(
          (r) =>
            r.current &&
            (r.current.contains(event.target as Node) ||
              r.current === event.target),
        )
      ) {
        return;
      }
      handler();
    };

    document.addEventListener("mousedown", listener);
    document.addEventListener("touchstart", listener);

    return () => {
      document.removeEventListener("mousedown", listener);
      document.removeEventListener("touchstart", listener);
    };
  }, [ref, handler]);
};

export default useClickOutside;
