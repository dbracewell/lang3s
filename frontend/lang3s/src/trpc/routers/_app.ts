import { AnalyticsRouter } from "@/modules/analytics/server/router";
import { authRouter } from "@/modules/auth/server/router";
import { DocumentsRouter } from "@/modules/documents/server/router";
import { jobsRouter } from "@/modules/jobs/server/router";
import { ontologyRouter } from "@/modules/ontology/server/router";
import { SearchRouter } from "@/modules/search/server/router";
import { createTRPCRouter } from "@/trpc/init";

export const appRouter = createTRPCRouter({
  documents: DocumentsRouter,
  search: SearchRouter,
  analytics: AnalyticsRouter,
  jobs: jobsRouter,
  ontology: ontologyRouter,
  auth: authRouter,
});

export type AppRouter = typeof appRouter;
