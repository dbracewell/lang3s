"use client";
import { Logo } from "@/components/logo";
import { useIsMobile } from "@/hooks/use-mobile";

export default function Home() {
  const isMobile = useIsMobile();
  return (
    <div className="flex h-full flex-1 flex-col items-center justify-center gap-2">
      <div className="shadow-shadow flex aspect-square size-fit flex-col items-center justify-center gap-3 rounded-full border-2 bg-slate-200 p-20 shadow-xl md:p-40 dark:bg-slate-800">
        {isMobile ? (
          <Logo
            height={300}
            className="fill-dodger-blue-500 stroke-dodger-blue-600 stroke-[10px]"
          />
        ) : (
          <Logo
            height={340}
            className="fill-dodger-blue-500 stroke-dodger-blue-600 stroke-[10px]"
          />
        )}
        <span className="text-5xl font-bold md:text-9xl">Lang3s</span>
      </div>
    </div>
  );
}
