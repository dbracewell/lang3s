import { Inngest } from "inngest";

// Create a client to send and receive events
export const inngest = new Inngest({
  id: "lang3s-frontend",
  //  eventKey: "AF10",
  //  signingKey: "AF10",
  //  baseUrl: "http://localhost:8288",
  //  isDev: true,
});
