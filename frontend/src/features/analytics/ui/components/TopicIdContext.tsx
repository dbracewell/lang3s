"use client";
import { useEffect } from "react";
import { useChatContext } from "@/features/chat/hooks/useChatContext";

export const TopicIdContext = ({
  sentences,
  entities,
}: {
  sentences: string[];
  entities: { entity: string; type: string; count: number }[];
}) => {
  const { setContext } = useChatContext();
  useEffect(() => {
    const s = sentences.join("\n");
    const e = entities.map((e) => `${e.entity}/${e.type}`).join("\n");
    setContext(`SENTENCES: ${s}\n\nENTITIES: ${e}`);
  }, [sentences, entities, setContext]);
  return null;
};
