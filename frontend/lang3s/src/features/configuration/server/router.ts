import { createTRPCRouter, protectedProcedure } from "@/lib/trpc/init";
import z from "zod";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { db } from "@/lib/db";
import { ConfigTable } from "@/lib/db/schemas/config";
import { eq } from "drizzle-orm";

export const configurationRouter = createTRPCRouter({
  getValue: protectedProcedure
    .input(z.object({ name: z.string().min(1) }))
    .query(async ({ input }) => {
      const [value] = await logAndRethrow(() => {
        return db
          .select({ value: ConfigTable.value })
          .from(ConfigTable)
          .where(eq(ConfigTable.name, input.name));
      });
      if (value) {
        return value.value;
      }
      return null;
    }),
  setValue: protectedProcedure
    .input(z.object({ name: z.string().min(1), value: z.any() }))
    .mutation(async ({ input }) => {
      const [value] = await logAndRethrow(() => {
        return db
          .insert(ConfigTable)
          .values({ ...input })
          .onConflictDoUpdate({
            target: ConfigTable.name,
            set: {
              value: input.value,
            },
          })
          .returning();
      });
      if (value) {
        return value.value;
      }
      return null;
    }),
});
