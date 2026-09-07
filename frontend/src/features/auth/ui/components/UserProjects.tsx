import { FullUserInfo } from "@/lib/types";
import React from "react";
import { FolderKanbanIcon } from "lucide-react";

export const UserProjects = ({ user }: { user: FullUserInfo }) => {
  return (
    <div className="flex flex-col">
      <div className="bg-heading flex items-center justify-between gap-2 rounded-t-lg border border-b-0 p-2 text-white">
        <h2 className="flex items-center gap-2 text-2xl font-semibold">
          <FolderKanbanIcon /> Projects
        </h2>
      </div>
      <div className="bg-muted flex h-full min-h-[200px] flex-1 flex-col gap-3 rounded-b-lg border dark:bg-zinc-800">
        <div className="flex flex-1 items-center justify-center">
          <div className="flex size-[150px] flex-col items-center justify-center gap-1">
            <FolderKanbanIcon size="50" className="text-muted-foreground" />
            <div className="text-muted-foreground text-lg">No Projects</div>
          </div>
        </div>
      </div>
    </div>
  );
};
