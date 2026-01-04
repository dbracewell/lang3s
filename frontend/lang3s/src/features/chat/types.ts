export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  id: string;
};
