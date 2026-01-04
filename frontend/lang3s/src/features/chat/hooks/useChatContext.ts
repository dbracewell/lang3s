import { atom, useAtom } from "jotai";

const chatContextAtom = atom<string>("");

export const useChatContext = () => {
  const [context, setContext] = useAtom(chatContextAtom);
  return {
    context,
    setContext,
  };
};
