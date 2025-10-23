import { db } from "@/db";
import { JobsTable, jobStatuses } from "@/db/schema";
import { ANNOTATION_QUEUE, performRedisCommand } from "@/lib/redis";
import { logAndRethrow } from "@/lib/try-catch";
import { Lang3sFile } from "@/modules/common/classes";
import {
  ApiEndpointSchema,
  apiMiddleWare,
  createTRPCRouter,
} from "@/trpc/init";
import { TRPCError } from "@trpc/server";
import { AnyColumn, desc, eq, sql } from "drizzle-orm";
import z from "zod";

const increment = (
  column: AnyColumn,
  value: number | undefined | null = undefined,
) => {
  if (value == null) {
    return undefined;
  }
  return sql`${column} + ${value}`;
};

export const jobsRouter = createTRPCRouter({
  get: apiMiddleWare
    .input(
      ApiEndpointSchema.extend({
        job_id: z.int(),
      }),
    )
    .query(async ({ input }) => {
      const { job_id } = input;

      const [job] = await logAndRethrow(
        db.select().from(JobsTable).where(eq(JobsTable.id, job_id)),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      return job;
    }),
  create: apiMiddleWare
    .input(
      ApiEndpointSchema.extend({
        name: z.string().min(1).max(255),
        metadata: z.record(z.string(), z.unknown()),
      }),
    )
    .mutation(async ({ input }) => {
      const { name, metadata } = input;

      const [job] = await logAndRethrow(
        db
          .insert(JobsTable)
          .values({
            name,
            metadata,
          })
          .returning(),
      );

      if (!job) {
        throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
      }

      return job;
    }),
  update: apiMiddleWare
    .input(
      ApiEndpointSchema.extend({
        job_id: z.int(),
        total_increment: z.int().nullish(),
        completed_increment: z.int().nullish(),
        failed_increment: z.int().nullish(),
        status: z.enum(jobStatuses).nullish(),
      }),
    )
    .mutation(async ({ input }) => {
      const {
        job_id,
        total_increment,
        completed_increment,
        failed_increment,
        status,
      } = input;

      const [job] = await logAndRethrow(
        db.select().from(JobsTable).where(eq(JobsTable.id, job_id)),
      );

      console.log(job);

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      if (job.status === "complete") {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      const newCompleted = job.completed + (completed_increment ?? 0);
      const newFailed = job.failed + (failed_increment ?? 0);
      const newTotal = job.total + (total_increment ?? 0);
      const newProcessed = newCompleted + newFailed;
      if (newProcessed > newTotal && status != "complete") {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      const [updatedJob] = await logAndRethrow(
        db
          .update(JobsTable)
          .set({
            total: increment(JobsTable.total, total_increment),
            completed: increment(JobsTable.completed, completed_increment),
            failed: increment(JobsTable.failed, failed_increment),
            status: status ?? undefined,
          })
          .where(eq(JobsTable.id, job_id))
          .returning(),
      );

      console.log(updatedJob);

      return updatedJob;
    }),
  delete: apiMiddleWare
    .input(ApiEndpointSchema.extend({ job_id: z.int() }))
    .mutation(async ({ input }) => {
      const { job_id } = input;

      const [job] = await logAndRethrow(
        db.select().from(JobsTable).where(eq(JobsTable.id, job_id)),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      if (job.status !== "complete") {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      await logAndRethrow(db.delete(JobsTable).where(eq(JobsTable.id, job_id)));

      return job;
    }),
  annotate: apiMiddleWare
    .input(
      ApiEndpointSchema.extend({
        job_id: z.int(),
        file: Lang3sFile,
      }),
    )
    .mutation(async ({ input }) => {
      const { job_id, file } = input;

      const [job] = await logAndRethrow(
        db.select().from(JobsTable).where(eq(JobsTable.id, job_id)),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      if (job.status === "complete") {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      await performRedisCommand(async (client) => {
        const task = { job_id: job_id, content: JSON.stringify(file) };
        await client.rPush(ANNOTATION_QUEUE, JSON.stringify(task));
      });

      const [updatedJob] = await logAndRethrow(
        db
          .update(JobsTable)
          .set({ total: increment(JobsTable.total, 1), status: "processing" })
          .where(eq(JobsTable.id, job_id))
          .returning(),
      );

      return updatedJob;
    }),

  getAll: apiMiddleWare.query(async () => {
    return logAndRethrow(
      db
        .select()
        .from(JobsTable)
        .orderBy((t) => [desc(t.createdAt)]),
    );
  }),
});
