import { FullUserInfo } from "@/features/common/types";
import React from "react";

export const UserProjects = ({ user }: { user: FullUserInfo }) => {
  return (
    <>
      <div className="bg-border my-2 h-[1px]" />
      <h1>Projects</h1>
    </>
  );
};
