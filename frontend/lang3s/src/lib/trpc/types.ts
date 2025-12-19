import { AppRouter } from "@/lib/trpc/routers/_app";
import { inferRouterOutputs } from "@trpc/server";

export type RouterOutputs = inferRouterOutputs<AppRouter>;
