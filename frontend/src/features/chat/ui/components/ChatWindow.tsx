"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useUser } from "@/features/auth/contexts/UserContext";
import ReactMarkdown from "react-markdown";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { capitalize } from "@/lib/utils/formatters";
import { CopyButton } from "@/components/buttons/CopyButton";
import { ArrowUpIcon, BotIcon, XIcon } from "lucide-react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import Link from "next/link";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import remarkBreaks from "remark-breaks";
import rehypeRaw from "rehype-raw";
import { useChatHistory } from "@/features/chat/hooks/useChatHistory";
import { useChatWindowStatus } from "@/features/chat/hooks/useChatWindowStatus";
import { useChatContext } from "@/features/chat/hooks/useChatContext";

export const ChatWindow = () => {
  const { context } = useChatContext();
  const { setOpen } = useChatWindowStatus();
  const { messages, addMessage, assistantMessages } = useChatHistory();
  const [prompt, setPrompt] = useState("");
  const bottomDiv = useRef<HTMLDivElement>(null);
  const user = useUser();
  const { mutate, isPending, error } = useMutation({
    mutationFn: (prompt: string) => chatFn(prompt),
  });

  const chatFn = async (prompt: string) => {
    return await fetch(`http://localhost:8003/agents`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: assistantMessages,
        prompt: prompt,
        userId: user.id,
        context: context,
      }),
    }).then(async (r) => {
      if (r.ok) {
        const j = await r.json();
        addMessage({
          id: randomAlphaUnderscore(),
          role: "assistant",
          content: j["response"],
        });
      }
    });
  };

  useEffect(() => {
    bottomDiv.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const submitPrompt = () => {
    mutate(prompt);
    addMessage({
      id: randomAlphaUnderscore(),
      role: "user",
      content: prompt,
    });
    setPrompt("");
  };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2 overflow-hidden pl-2">
      <div className="bg-heading flex items-center justify-between gap-2 rounded-lg p-2 font-bold text-white">
        <h2 className="flex items-center gap-2">
          <BotIcon className="size-5" /> Agent
        </h2>
        <Button
          type="button"
          onClick={() => {
            setOpen(false);
          }}
          variant="ghost"
          size="icon-sm"
        >
          <XIcon />
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 grow flex-col">
        <div className="scrollable flex flex-1 flex-col gap-2 p-3">
          {context}
          {messages.map((h) => {
            if (h.role === "assistant") {
              return (
                <div key={h.id}>
                  <h2 className="mb-2 px-2 font-semibold">
                    Assistant{" "}
                    <CopyButton
                      text={h.content}
                      variant={"ghost"}
                      size="icon-xs"
                    />
                  </h2>
                  <div
                    key={h.id}
                    className="prose dark:prose-invert bg-muted flex max-w-lg flex-col rounded-lg p-2 text-balance"
                  >
                    <ReactMarkdown
                      rehypePlugins={[rehypeRaw]}
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={{
                        a: ({ node, ...props }) => (
                          <Link
                            href={props.href!}
                            className="link"
                            {...props}
                          />
                        ),
                      }}
                    >
                      {h.content}
                    </ReactMarkdown>
                  </div>
                </div>
              );
            }
            return (
              <div key={h.id} className="flex flex-col items-end justify-end">
                <span className="mb-2 px-2 font-semibold">
                  {capitalize(user.name)}
                </span>
                <div className="bg-accent ml-auto flex max-w-md justify-end rounded-lg p-2">
                  {h.content}
                </div>
              </div>
            );
          })}
          {isPending && (
            <div className="text-dodger-blue-500 animate-pulse text-2xl font-bold">
              ...
            </div>
          )}
          {error && <p>{error.message}</p>}
          <div ref={bottomDiv} />
        </div>
      </div>
      <div className="flex min-h-0 w-full items-end gap-3">
        <InputGroup className="bg-card">
          <InputGroupTextarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                submitPrompt();
              } else if (e.key === "ArrowUp" && e.shiftKey) {
                setPrompt(
                  messages.findLast((p) => p.role === "user")?.content ?? "",
                );
              }
            }}
          />
          <InputGroupAddon align="block-end">
            <div className="flex w-full justify-end">
              <InputGroupButton
                disabled={isPending || !prompt.trim()}
                variant="listButton"
                className="flex size-8! items-center justify-center rounded-full p-0!"
                onClick={submitPrompt}
              >
                <ArrowUpIcon className="size-4" />
                <span className="sr-only">Send</span>
              </InputGroupButton>
            </div>
          </InputGroupAddon>
        </InputGroup>
      </div>
    </div>
  );
};
