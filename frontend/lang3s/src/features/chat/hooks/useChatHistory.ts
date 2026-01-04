import { atom, useAtomValue, useSetAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { CHAT_HISTORY_STORAGE_KEY } from "@/features/chat/constants";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { ChatMessage } from "@/features/chat/types";

const agentHistoryAtom = atomWithStorage<ChatMessage[]>(
  CHAT_HISTORY_STORAGE_KEY,
  [
    {
      role: "assistant",
      content: "How may I assist you?",
      id: randomAlphaUnderscore(),
    },
  ],
);

const clearMessagesAtom = atom(null, (_, set) => {
  set(agentHistoryAtom, []);
});

const addMessageAtom = atom(null, (_, set, message: ChatMessage) => {
  set(agentHistoryAtom, (prev) => [...prev, message]);
});

const assistantMessageAtom = atom((get) =>
  get(agentHistoryAtom)
    .filter((m) => m.role === "assistant")
    .slice(1),
);

export const useChatHistory = () => {
  const messages = useAtomValue(agentHistoryAtom);
  const clearMessages = useSetAtom(clearMessagesAtom);
  const addMessage = useSetAtom(addMessageAtom);
  const assistantMessages = useAtomValue(assistantMessageAtom);
  return {
    messages,
    addMessage,
    clearMessages,
    assistantMessages,
  };
};
