import { authRouter } from "@/features/auth/server/authRouter";
import { createTRPCRouter } from "@/lib/trpc/init";

export const appRouter = createTRPCRouter({
  auth: authRouter,
});

export type AppRouter = typeof appRouter;
