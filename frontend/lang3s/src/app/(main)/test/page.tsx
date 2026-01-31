"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useUser } from "@/features/auth/contexts/UserContext";
import { agentStatusAtom } from "@/features/events/stores/chat-stores";
import { useMutation } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

const Page = () => {
  const [prompt, setPrompt] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const { mutate, isPending, error } = useMutation({
    mutationFn: (prompt: string) => chatFn(prompt),
  });
  const user = useUser();
  const statuses = useAtomValue(agentStatusAtom);

  const chatFn = async (prompt: string) => {
    console.log(prompt);
    return await fetch(`http://localhost:8003/agents/discover`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: "This is a test",
        userId: user.id,
      }),
    }).then(async (r) => {
      if (r.ok) {
        const j = await r.json();
        setHistory((prev) => [...prev, j["response"]]);
        return j["response"];
      }
    });
  };
  return (
    <div className="m-5 flex h-screen flex-col overflow-hidden p-3">
      <div className="flex flex-1 grow flex-col">
        <div className="scrollable flex flex-1 flex-col">
          <h3>Agent Response</h3>
          {history.map((h, i) => (
            <p className="py-1" key={i}>
              {h}
            </p>
          ))}
          {isPending && <div className="animate-pulse">...</div>}
          {error && <p>{error.message}</p>}
        </div>
      </div>
      <div className="flex min-h-0 w-full flex-col">
        <Textarea
          className="h-37.5 resize-none"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <Button
          disabled={isPending || !prompt.trim()}
          onClick={() => {
            mutate(prompt);
            setPrompt("");
          }}
        >
          Send
        </Button>
        <div className="mt-5 flex min-h-0 w-full flex-col overflow-hidden">
          {statuses.map((stat, i) => (
            <div key={stat.id} className="flex h-full min-h-0 flex-1 flex-col">
              <p className="py-1">{stat.progress * 100}%</p>
              <div className="prose dark:prose-invert scrollable flex-1">
                <ReactMarkdown>{stat.response}</ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Page;
