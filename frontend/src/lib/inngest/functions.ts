import { inngest } from "./client";

const BASE_PATH = `${process.env.NEXT_PUBLIC_BACKEND_URL}/analytics`;

export const update = inngest.createFunction(
  { id: "update-analytics" },
  { event: "analytics/update" },
  async ({ event, step }) => {},
);
