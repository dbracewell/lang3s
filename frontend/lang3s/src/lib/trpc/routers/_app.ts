import { AnalyticsRouter } from "@/features/analytics/server/analyticsRouter";
import { authRouter } from "@/features/auth/server/authRouter";
import { DocumentsRouter } from "@/features/documents/server/documentsRouter";
import { jobsRouter } from "@/features/jobs/server/jobsRouter";
import { ontologyRouter } from "@/features/ontology/server/ontologyRouter";
import { SearchRouter } from "@/features/search/server/searchRouter";
import { createTRPCRouter } from "@/lib/trpc/init";
import { reportsRouter } from "@/features/reports/server/reportsRouter";
import { systemRouter } from "@/features/common/server/systemRouter";

export const appRouter = createTRPCRouter({
  documents: DocumentsRouter,
  search: SearchRouter,
  analytics: AnalyticsRouter,
  jobs: jobsRouter,
  ontology: ontologyRouter,
  auth: authRouter,
  reports: reportsRouter,
  system: systemRouter,
});

export type AppRouter = typeof appRouter;
