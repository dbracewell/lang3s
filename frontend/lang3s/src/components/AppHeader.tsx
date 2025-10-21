"use client";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { SearchBar } from "@/modules/search/ui/components/SearchBar";
import { Suspense } from "react";

export const AppHeader = () => {
   const { state } = useSidebar();
   return (
      <header className="sticky top-0 z-20 h-14 bg-zinc-50 p-5 pl-1.5 flex items-center gap-3 w-full text-white border-b">
         <SidebarTrigger className="text-slate-700" />
         <div className="mx-auto w-[400px] text-black">
            <Suspense>
               <SearchBar />
            </Suspense>
         </div>
      </header>
   );
};
