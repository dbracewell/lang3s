import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import Link from "next/link";

type PageNumbersProps = {
  totalPages: number;
  currentPage: number;
  pageLink: (page: number) => string;
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
      {start == 1 ? (
        <ChevronLeftIcon />
      ) : (
        <Link href={pageLink(start)} className="link">
          <ChevronLeftIcon />
        </Link>
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
          <Link
            key={page}
            href={pageLink(page)}
            prefetch={true}
            className="link no-underline!"
          >
            {page}
          </Link>
        );
      })}
      {end === totalPages ? (
        <ChevronRightIcon />
      ) : (
        <Link href={pageLink(end)} className="link">
          <ChevronRightIcon />
        </Link>
      )}
    </div>
  );
};
