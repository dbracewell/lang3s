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
  header?: string;
};
export const DocumentScrollHeader = ({
  count,
  scrollRef,
  header = "Total Documents",
  isScrolled,
  isSearch = false,
}: DocumentScrollHeaderProps) => {
  return (
    <div className="flex h-10 items-center justify-between p-2 text-lg font-bold">
      {isSearch && "Search Resulted in "}
      {formatNumber(count)} {header}{" "}
      <Button
        className={cn("rounded-full", isScrolled ? "visible" : "hidden")}
        variant="listButton"
        size="icon-sm"
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
