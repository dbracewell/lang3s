import { db } from "@/lib/db";
import { JobsTable, jobStatuses } from "@/lib/db/schema";
import { ANNOTATION_QUEUE, getGlobalConnection } from "@/lib/redis";
import { logAndRethrow } from "@/lib/utils/try-catch";
import {
  getAdminAccount,
  getUserApiKeys,
  getUserByApiKey,
  isSystemApiKey,
  requirePermissions,
} from "@/features/auth/server/actions";
import { Lang3sFile } from "@/features/common/classes";
import { BasicUserInfo } from "@/features/common/types";
import { apiProcedure, createTRPCRouter } from "@/lib/trpc/init";
import { TRPCError } from "@trpc/server";
import { and, AnyColumn, count, desc, eq, ne, or, sql } from "drizzle-orm";
import z from "zod";
import { publishMessage } from "@/lib/events/publish";

const increment = (
  column: AnyColumn,
  value: number | undefined | null = undefined,
) => {
  if (value == null) {
    return undefined;
  }
  return sql`${column} + ${value}`;
};

const buildWhereClause = async (
  job_id?: number,
  user?: BasicUserInfo,
  apiKey?: string,
) => {
  const where = [];

  if (user == null && apiKey == null) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }

  if (job_id != null) {
    where.push(eq(JobsTable.id, job_id));
  }

  if (apiKey && !(await isSystemApiKey(apiKey))) {
    where.push(eq(JobsTable.apiKey, apiKey));
  }

  if (user?.id && user.role !== "admin") {
    const allKeys = await getUserApiKeys(user.id);
    const orEd = [eq(JobsTable.userId, user?.id)];
    allKeys.forEach((key) => {
      orEd.push(eq(JobsTable.apiKey, key.key));
    });
    where.push(or(...orEd));
  }

  return where;
};

export const jobsRouter = createTRPCRouter({
  get: apiProcedure
    .input(
      z.object({
        job_id: z.int(),
      }),
    )
    .query(async ({ ctx, input }) => {
      const { user, apiKey } = ctx;
      const { job_id } = input;
      await requirePermissions(user, apiKey, ["jobs:view"]);

      const where = await buildWhereClause(job_id, user, apiKey);
      const [job] = await logAndRethrow(() =>
        db
          .select()
          .from(JobsTable)
          .where(and(...where)),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      return job;
    }),
  create: apiProcedure
    .input(
      z.object({
        name: z.string().min(1).max(255),
        total: z.number().min(0).optional(),
        status: z.enum(jobStatuses).optional(),
        metadata: z.record(z.string(), z.unknown()),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const { user, apiKey } = ctx;
      const { name, metadata, total, status } = input;

      await requirePermissions(user, apiKey, ["jobs:create"]);
      let effectiveUser = user;
      if (effectiveUser == null) {
        if (await isSystemApiKey(apiKey)) {
          effectiveUser = await getAdminAccount();
        } else if (apiKey != null) {
          effectiveUser = await getUserByApiKey(apiKey);
        }
      }
      if (effectiveUser == null) {
        throw new TRPCError({ code: "UNAUTHORIZED" });
      }

      const effectiveApikey = (await isSystemApiKey(apiKey))
        ? undefined
        : apiKey;

      const [job] = await logAndRethrow(() =>
        db
          .insert(JobsTable)
          .values({
            name,
            metadata,
            total,
            status,
            userId: effectiveUser?.id,
            apiKey: effectiveApikey,
          })
          .returning(),
      );

      if (!job) {
        throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
      }

      await publishJobStatus(job);

      return job;
    }),
  update: apiProcedure
    .input(
      z.object({
        job_id: z.int(),
        total_increment: z.int().nullish(),
        completed_increment: z.int().nullish(),
        failed_increment: z.int().nullish(),
        status: z.enum(jobStatuses).nullish(),
        metadata: z.record(z.string(), z.unknown()).nullish(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const { user, apiKey } = ctx;
      const {
        job_id,
        total_increment,
        completed_increment,
        failed_increment,
        status,
        metadata,
      } = input;

      await requirePermissions(user, apiKey, ["jobs:create"]);

      const where = await buildWhereClause(job_id, user, apiKey);
      const [job] = await logAndRethrow(() =>
        db
          .select()
          .from(JobsTable)
          .where(and(...where)),
      );

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

      const [updatedJob] = await logAndRethrow(() =>
        db
          .update(JobsTable)
          .set({
            total: increment(JobsTable.total, total_increment),
            completed: increment(JobsTable.completed, completed_increment),
            failed: increment(JobsTable.failed, failed_increment),
            status: status ?? undefined,
            startedAt: status === "processing" ? new Date() : undefined,
            completedAt: ["complete", "failed"].includes(status ?? "")
              ? new Date()
              : undefined,
            metadata: metadata ?? undefined,
          })
          .where(and(...where))
          .returning(),
      );

      if (
        ["complete", "failed"].includes(status ?? "") &&
        job.jobType === "annotation"
      ) {
        await logAndRethrow(async () => {
          // await db.execute(
          //   sql`DROP INDEX IF EXISTS text_annotation_embedding_index;`,
          // );
          return db.execute(
            sql`CREATE INDEX IF NOT EXISTS "text_annotation_embedding_index" ON "text_annotations" USING hnsw ("embedding" halfvec_cosine_ops);`,
          );
        });
      }

      await publishJobStatus(updatedJob);

      if (metadata != null && metadata["all_documents_sent"] == true) {
        try {
          const redis = await getGlobalConnection();
          const task = {
            job_id: job_id,
            __status: "completed",
          };
          await redis.rPush(ANNOTATION_QUEUE, JSON.stringify(task));
        } catch (err) {
          console.error(err);
          return job;
        }
      }

      return updatedJob;
    }),
  delete: apiProcedure
    .input(z.object({ job_id: z.int() }))
    .mutation(async ({ ctx, input }) => {
      const { user, apiKey } = ctx;
      const { job_id } = input;

      await requirePermissions(user, apiKey, ["jobs:delete"]);

      const where = await buildWhereClause(job_id, user, apiKey);
      const [job] = await logAndRethrow(() =>
        db
          .delete(JobsTable)
          .where(and(...where))
          .returning(),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      return job;
    }),
  annotate: apiProcedure
    .input(
      z.object({
        job_id: z.int(),
        files: z.array(Lang3sFile),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const { user, apiKey } = ctx;
      const { job_id, files } = input;

      await requirePermissions(
        user,
        apiKey,
        ["jobs:create", "data:load"],
        true,
      );

      const where = await buildWhereClause(job_id, user, apiKey);
      const [job] = await logAndRethrow(() =>
        db
          .select()
          .from(JobsTable)
          .where(and(...where)),
      );

      if (!job) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      if (job.status === "complete") {
        throw new TRPCError({ code: "BAD_REQUEST" });
      }

      const [annotationJobs] = await logAndRethrow(() =>
        db
          .select({ count: count() })
          .from(JobsTable)
          .where(
            and(
              ne(JobsTable.id, job.id),
              eq(JobsTable.jobType, "annotation"),
              eq(JobsTable.status, "processing"),
            ),
          ),
      );

      if (annotationJobs != null && annotationJobs.count > 0) {
        throw new TRPCError({ code: "CONFLICT" });
      }

      try {
        const redis = await getGlobalConnection();
        for (const file of files) {
          const task = { job_id: job_id, content: JSON.stringify(file) };
          await redis.rPush(ANNOTATION_QUEUE, JSON.stringify(task));
        }
      } catch (err) {
        console.error(err);
        return job;
      }

      if (job.status === "waiting") {
        await logAndRethrow(async () => {
          await db.execute(
            sql`DROP INDEX IF EXISTS text_annotation_embedding_index;`,
          );
        });
      }

      const [updatedJob] = await logAndRethrow(() =>
        db
          .update(JobsTable)
          .set({
            total: increment(JobsTable.total, files.length),
            status: "processing",
            jobType: "annotation",
            startedAt: job.status === "waiting" ? new Date() : undefined,
          })
          .where(and(...where))
          .returning(),
      );

      await publishJobStatus(updatedJob);

      return updatedJob;
    }),

  getAll: apiProcedure.query(async ({ ctx }) => {
    const { user, apiKey } = ctx;
    await requirePermissions(user, apiKey, ["jobs:view"]);
    const where = await buildWhereClause(undefined, user, apiKey);
    return logAndRethrow(() =>
      db
        .select()
        .from(JobsTable)
        .where(and(...where))
        .orderBy((t) => [desc(t.createdAt)]),
    );
  }),
});

const publishJobStatus = async (job: typeof JobsTable.$inferSelect) => {
  const progress = job.total > 0 ? (job.completed + job.failed) / job.total : 0;
  console.log(progress, job.status);
  try {
    await publishMessage({
      messageType: "job:update",
      payload: {
        jobId: job.id,
        progress: progress * 100,
        status: job.status,
      },
      userId: job.userId,
    });
  } catch (e) {
    console.error(e);
  }
};
