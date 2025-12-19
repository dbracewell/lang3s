import { Progress } from "@/components/ui/progress";
import { RouterOutputs } from "@/lib/trpc/types";
import React from "react";

export const ProgressCell = ({
  row,
}: {
  row: RouterOutputs["jobs"]["getAll"][number];
}) => {
  const pct = Math.floor((row.total > 0 ? row.completed / row.total : 0) * 100);
  return (
    <div className="relative flex w-full items-center">
      <Progress value={pct} />
      <div
        className="border-dodger-blue-600 bg-dodger-blue-600 absolute top-1/2 w-10 -translate-y-1/2 rounded-sm border p-0.5 text-center text-xs text-white shadow"
        style={{
          left: `min( max( ${pct}% - 30px , 3px ), 100% - 40px )`,
        }}
      >
        {pct}%
      </div>
    </div>
  );
};
