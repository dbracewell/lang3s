import { Inngest } from "inngest";

// Create a client to send and receive events
export const inngest = new Inngest({
  id: "lang3s-frontend",
  baseUrl: "http://192.168.0.100:8288",
  eventKey: "A1B2C3",
});
