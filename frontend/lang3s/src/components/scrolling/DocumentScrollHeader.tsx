import { RefObject } from "react";
import { formatNumber } from "@/lib/utils/formatters";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { ArrowUpIcon } from "lucide-react";

type DocumentScrollHeaderProps = {
  count: number;
  scrollRef: RefObject<HTMLDivElement | null>;
  isScrolled: boolean;
  isSearch?: boolean;
};
export const DocumentScrollHeader = ({
  count,
  scrollRef,
  isScrolled,
  isSearch = false,
}: DocumentScrollHeaderProps) => {
  return (
    <div className="bg-heading flex h-10 items-center justify-between rounded-lg border p-2 text-lg font-bold text-white">
      {isSearch && "Search Resulted in "}
      {formatNumber(count)} Total Documents{" "}
      <Button
        className={cn(
          "hover:bg-white/50! dark:hover:bg-white/30!",
          isScrolled ? "visible" : "hidden",
        )}
        variant="ghost"
        size="icon-xs"
        onClick={() => {
          scrollRef.current?.scrollTo({
            top: 0,
          });
        }}
      >
        <ArrowUpIcon />
      </Button>
    </div>
  );
};
