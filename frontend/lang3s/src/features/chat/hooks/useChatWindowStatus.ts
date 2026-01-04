import { atom, useAtom } from "jotai";

const chatWindowOpenAtom = atom<boolean>(false);

export const useChatWindowStatus = () => {
  const [open, setOpen] = useAtom(chatWindowOpenAtom);

  return {
    open,
    setOpen,
  };
};
