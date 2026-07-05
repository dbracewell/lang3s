import { inngest } from "./client";

const BASE_PATH = `${process.env.PYTHON_SERVER}/analytics`;

export const update = inngest.createFunction(
  { id: "update-analytics" },
  { event: "analytics/update" },
  async ({ event, step }) => {},
);
