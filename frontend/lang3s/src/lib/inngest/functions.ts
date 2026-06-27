import { inngest } from "./client";
import { publishMessage } from "@/lib/events/publish";
import { db } from "@/lib/db";
import { eq } from "drizzle-orm";
import { roleHasPermissions } from "@/features/auth/server/actions";
import { NonRetriableError } from "inngest";
import { UserRole } from "@/lib/auth/permissions";
import { user } from "@/lib/db/schemas/auth";
import { ConfigTable } from "@/lib/db/schemas/config";
import { putJson } from "@/lib/utils/superFetch";

const BASE_PATH = `${process.env.PYTHON_SERVER}/analytics`;

export const update = inngest.createFunction(
  { id: "update-analytics" },
  { event: "analytics/update" },
  async ({ event, step }) => {
    try {
      await step.run("update_status", async () => {
        return db.insert(ConfigTable).values({
          name: "update-analytics",
          value: "true",
        });
      });
    } catch (e) {
      await publishMessage({
        messageType: "analytics_update",
        payload: { completed: true },
        userId: event.data.userId,
      });
      throw new NonRetriableError("Updating in progress");
    }

    const userById = await step.run("get-user-role", async () => {
      return db.query.user.findFirst({
        where: eq(user.id, event.data.userId),
      });
    });

    try {
      if (
        userById == null ||
        !(await roleHasPermissions(userById.role as UserRole, [
          "model:create",
          "data:load",
          "data:update",
        ]))
      ) {
        throw new NonRetriableError("UNAUTHORIZED");
      }

      await step.run("update-analytics-view", async () => {
        await putJson(`${BASE_PATH}/updatestats`);
        // await db.refreshMate
        // rializedView(AnnotationCounts).concurrently();
        // await db.refreshMaterializedView(AnnotationCoOccurrence).concurrently();
      });

      await step.run("publish-update-message", async () => {
        await publishMessage({
          messageType: "analytics_update",
          payload: { completed: true },
          userId: event.data.userId,
        });
      });
    } catch (e) {
      await step.run("publish-update-message", async () => {
        await publishMessage({
          messageType: "analytics_update",
          payload: { completed: false },
          userId: event.data.userId,
        });
      });
      throw e;
    } finally {
      await step.run("delete_status", async () => {
        return db
          .delete(ConfigTable)
          .where(eq(ConfigTable.name, "update-analytics"));
      });
    }
  },
);
