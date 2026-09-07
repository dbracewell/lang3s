"use client";
import React from "react";
import { eventBus } from "@/lib/events/eventBus";
import { useUser } from "@/features/auth/contexts/UserContext";

const Page = () => {
  const [messages, setMessages] = React.useState<string[]>([]);
  const user = useUser();
  React.useEffect(() => {
    return eventBus.on("agent:update", (payload) => {
      setMessages((prev) => [...prev, JSON.stringify(payload)]);
    });
  }, []);

  return (
    <div className="flex flex-1 flex-col">
      {user.id}
      {messages.map((v, i) => (
        <div key={i}>{v}</div>
      ))}
    </div>
  );
};

export default Page;
