import { Inngest } from "inngest";
import { t3env } from "@/lib/t3env";

// Create a client to send and receive events
export const inngest = new Inngest({
  id: "lang3s-frontend",
  baseUrl: t3env.INNGEST_URL,
  eventKey: t3env.INNGEST_SIGNING_KEY,
});
