import { Logo } from "@/components/logo";

export default function Home() {
  return (
    <div className="flex h-full flex-1 flex-col items-center justify-center gap-2">
      <div className="flex flex-col items-center justify-center rounded-full border-2 bg-slate-200 p-40 shadow-2xl">
        <Logo
          height={340}
          className="fill-dodger-blue-500 stroke-dodger-blue-600 stroke-[10px]"
        />
        <span className="text-9xl font-bold">Lang3s</span>
      </div>
    </div>
  );
}
