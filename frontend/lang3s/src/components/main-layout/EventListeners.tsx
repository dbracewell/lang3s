import React from "react";
import { JobStatusListener } from "@/features/jobs/listeners/jobStatusListener";
import { AgentStatusUpdateListener } from "@/features/events/listeners/agentStatusUpdateListener";

export const EventListeners = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <JobStatusListener />
      <AgentStatusUpdateListener />
      {children}
    </>
  );
};
