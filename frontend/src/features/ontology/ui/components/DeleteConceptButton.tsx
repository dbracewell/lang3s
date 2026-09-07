"use client";
import { useDeleteConcept } from "@/features/ontology/hooks/useDeleteConcept";
import { LoadingButton } from "@/components/ui/loading-button";
import { Trash2Icon } from "lucide-react";
import React from "react";

export const DeleteConceptButton = ({ nodeId }: { nodeId: number }) => {
  const { Dialog, isPending, mutateFn } = useDeleteConcept();
  return (
    <div>
      <Dialog />
      <LoadingButton
        isLoading={isPending}
        variant="ghost"
        className="hover:bg-destructive! bg-l rounded-md hover:text-white"
        size="icon-xs"
        type="button"
        onClick={() => mutateFn(nodeId)}
      >
        <Trash2Icon />
      </LoadingButton>
    </div>
  );
};
