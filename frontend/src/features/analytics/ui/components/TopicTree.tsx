"use client";
import { TopicNode } from "@/features/analytics/types";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ArrowBigUpIcon } from "lucide-react";

export const TopicTree = ({ tree }: { tree: TopicNode }) => {
  const [currentNode, setCurrentNode] = useState<TopicNode>(tree);
  const [path, setPath] = useState<TopicNode[]>([tree]);
  const [parentNode, setParentNode] = useState<TopicNode | null>(null);

  return (
    <div className="flex flex-1 flex-col">
      {currentNode && (
        <Button
          variant="ghost"
          onClick={() => {
            setCurrentNode(parentNode!);
            setPath((prev) => prev.slice(0, -1));
          }}
          disabled={parentNode === null}
        >
          <ArrowBigUpIcon /> {currentNode.name}
        </Button>
      )}
      <div className="flex flex-1 flex-col">
        {currentNode &&
          currentNode.children.map((child) => (
            <div
              key={child.id}
              className="cursor-pointer rounded border p-2"
              onClick={() => {
                setParentNode(currentNode);
                setPath((prev) => [...prev, child]);
                setCurrentNode(child);
              }}
            >
              {child.name} ({child.topics?.length} topics)
            </div>
          ))}
      </div>
    </div>
  );
};
