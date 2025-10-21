import { AnalyticsRouter } from "@/modules/analytics/server/router";
import { DocumentsRouter } from "@/modules/documents/server/router";
import { jobsRouter } from "@/modules/jobs/server/router";
import { SearchRouter } from "@/modules/search/server/router";
import { createTRPCRouter } from "@/trpc/init";

export const appRouter = createTRPCRouter({
  documents: DocumentsRouter,
  search: SearchRouter,
  analytics: AnalyticsRouter,
  jobs: jobsRouter,
});

export type AppRouter = typeof appRouter;
