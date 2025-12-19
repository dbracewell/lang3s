"use client";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { capitalize } from "@/lib/utils/formatters";
import { SearchBar } from "@/features/search/ui/components/SearchBar";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

const getHeading = (path: string[]) => {
  const length = path.length;
  if (length === 0) {
    return "Home";
  }
  if (length > 1) {
    if (path[length - 2] === "documents") {
      return "Documents";
    }
  }
  return path[length - 1];
};

export const AppHeader = () => {
  const pathname = usePathname().split("/");
  const heading = getHeading(pathname);
  return (
    <header className="sticky top-0 z-20 flex h-14 w-full items-center gap-3 border-b bg-zinc-50 p-5 pl-1.5 text-white">
      <SidebarTrigger className="text-slate-700" />
      <h2 className="text-lg font-bold text-slate-900">
        {capitalize(heading)}
      </h2>
      <div className="mx-auto w-[400px] text-black">
        <Suspense>
          <SearchBar />
        </Suspense>
      </div>
    </header>
  );
};
