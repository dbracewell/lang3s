"use client";

import { useCallback, useRef, useState } from "react";

export const useScrollToTop = () => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);

  const onScroll = useCallback(() => {
    if (scrollRef.current) {
      const container = scrollRef.current;
      setIsScrolled(container.scrollTop >= container.clientHeight);
    }
  }, []);

  return { isScrolled, scrollRef, onScroll };
};
