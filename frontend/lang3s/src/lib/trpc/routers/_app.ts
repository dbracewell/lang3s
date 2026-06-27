import { authRouter } from "@/features/auth/server/authRouter";
import { SearchRouter } from "@/features/search/server/searchRouter";
import { createTRPCRouter } from "@/lib/trpc/init";

export const appRouter = createTRPCRouter({
  search: SearchRouter,
  auth: authRouter,
});

export type AppRouter = typeof appRouter;
