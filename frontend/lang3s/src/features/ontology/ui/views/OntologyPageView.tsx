"use client";
import { Button } from "@/components/ui/button";
import { useTRPCMutation } from "@/trpc/use-mutation";
import { useTRPCQuery } from "@/trpc/use-queries";
import React from "react";

export const OntologyPageView = () => {
  const { data, isLoading } = useTRPCQuery((trpc) =>
    trpc.ontology.getTopLevel.queryOptions(),
  );
  const m = useTRPCMutation((trpc) => ({
    mutation: trpc.ontology.addConcept.mutationOptions(),
  }));
  return (
    <div className="scrollable h-full min-h-0 flex-1">
      <Button
        onClick={() => {
          m.mutate({
            name: "Entity",
            parentName: "Root",
            description: "An entity",
          });
        }}
      >
        Add Entity
      </Button>
      {data?.map((e) => (
        <div key={e.id}>
          {e.name} {e.path}
        </div>
      ))}
    </div>
  );
};
