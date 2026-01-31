import { db } from "@/lib/db";
import { PrecomputedStatsTable } from "@/lib/db/schemas/stats";
import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { eq } from "drizzle-orm";
import z from "zod";

export const precomputedStatsRouter = createTRPCRouter({
  get: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1),
      }),
    )
    .query(async ({ input }) => {
      const [stats] = await logAndRethrow(() =>
        db
          .select({ value: PrecomputedStatsTable.value })
          .from(PrecomputedStatsTable)
          .where(eq(PrecomputedStatsTable.name, input.name)),
      );
      if (!stats) {
        return {};
      }
      return stats.value;
    }),
});
