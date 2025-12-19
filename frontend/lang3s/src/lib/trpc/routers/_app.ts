import { AnalyticsRouter } from "@/features/analytics/server/router";
import { authRouter } from "@/features/auth/server/router";
import { DocumentsRouter } from "@/features/documents/server/router";
import { jobsRouter } from "@/features/jobs/server/router";
import { ontologyRouter } from "@/features/ontology/server/router";
import { SearchRouter } from "@/features/search/server/router";
import { createTRPCRouter } from "@/lib/trpc/init";

export const appRouter = createTRPCRouter({
  documents: DocumentsRouter,
  search: SearchRouter,
  analytics: AnalyticsRouter,
  jobs: jobsRouter,
  ontology: ontologyRouter,
  auth: authRouter,
});

export type AppRouter = typeof appRouter;
