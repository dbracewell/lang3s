import React from "react";
import { JobStatusListener } from "@/features/jobs/listeners/jobStatusListener";
import { OntologyUpdateListener } from "@/features/ontology/OntologyUpdateListener";

export const EventListeners = ({ children }: { children: React.ReactNode }) => {
  return (
    <>
      <JobStatusListener />
      <OntologyUpdateListener />
      {children}
    </>
  );
};
