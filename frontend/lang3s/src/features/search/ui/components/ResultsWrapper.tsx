"use client";
import React from "react";
import { DocumentScrollHeader } from "@/components/scrolling/DocumentScrollHeader";
import { useScrollToTop } from "@/hooks/useScrollToTop";
import { cn } from "@/lib/utils/cn";

export const ResultsWrapper = ({
  total,
  header,
  children,
}: {
  total: number;
  header?: string;
  children: React.ReactNode;
}) => {
  const { scrollRef, onScroll, isScrolled } = useScrollToTop();
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-1">
      <DocumentScrollHeader
        count={total}
        header={header}
        scrollRef={scrollRef}
        isScrolled={isScrolled}
        isSearch={true}
      />
      <div className="flex min-h-0 flex-1 flex-col">
        <div
          className="scrollable bg-alternate-row/50 dark:bg-row/20 flex flex-1 flex-col rounded-lg border pr-2"
          ref={scrollRef}
          onScroll={onScroll}
        >
          {children}
        </div>
      </div>
    </div>
  );
};
