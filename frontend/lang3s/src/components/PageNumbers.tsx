import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import Link from "next/link";

type PageNumbersProps = {
  totalPages: number;
  currentPage: number;
  pageLink: (page: number) => void;
  maxDisplay?: number;
};

export const PageNumbers = ({
  currentPage,
  totalPages,
  pageLink,
  maxDisplay = 10,
}: PageNumbersProps) => {
  const pages: number[] = [];

  let start = 1;
  let end = 0;

  if (totalPages < maxDisplay) {
    end = totalPages;
  } else {
    start = currentPage - Math.round((maxDisplay - 1) / 2);
    end = start + maxDisplay - 1;
    if (start < 1) {
      start = 1;
      end = maxDisplay;
    }
    if (end > totalPages) {
      end = totalPages;
      start = totalPages - maxDisplay + 1;
    }
  }

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  return (
    <div className="flex items-center justify-end gap-1 text-lg">
      {currentPage - 1 < 0 ? (
        <ChevronLeftIcon />
      ) : (
        <button
          type="button"
          className="link"
          onClick={() => pageLink(currentPage - 1)}
        >
          <ChevronLeftIcon />
        </button>
      )}
      {pages.map((page) => {
        if (page === currentPage) {
          return (
            <div key="current_page" className="underline">
              {page}
            </div>
          );
        }
        return (
          <button
            key={page}
            type="button"
            className="link no-underline!"
            onClick={() => pageLink(page)}
          >
            {page}
          </button>
        );
      })}
      {currentPage + 1 > totalPages ? (
        <ChevronRightIcon />
      ) : (
        <button
          type="button"
          className="link"
          onClick={() => pageLink(currentPage + 1)}
        >
          <ChevronRightIcon />
        </button>
      )}
    </div>
  );
};
