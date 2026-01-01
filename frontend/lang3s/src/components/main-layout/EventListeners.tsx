import React from "react";
import { JobStatusListener } from "@/features/jobs/listeners/jobStatusListener";

export const EventListeners = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <JobStatusListener />
      {children}
    </>
  );
};
