import { inngest } from "./client";
import { publishMessage } from "@/lib/events/publish";
import { db } from "@/lib/db";
import { eq } from "drizzle-orm";
import { roleHasPermissions } from "@/features/auth/server/actions";
import { NonRetriableError } from "inngest";
import { UserRole } from "@/lib/auth/permissions";
import { user } from "@/lib/db/schemas/auth";
import {
  AnnotationCoOccurrence,
  AnnotationCounts,
} from "@/lib/db/schemas/views";

export const update = inngest.createFunction(
  { id: "update-analytics" },
  { event: "analytics/update" },
  async ({ event, step }) => {
    const userById = await step.run("get-user-role", async () => {
      return await db.query.user.findFirst({
        where: eq(user.id, event.data.userId),
      });
    });

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
      await db.refreshMaterializedView(AnnotationCounts).concurrently();
      await db.refreshMaterializedView(AnnotationCoOccurrence).concurrently();
    });

    await step.run("publish-update-message", async () => {
      await publishMessage({
        messageType: "analytics_update",
        payload: { completed: true },
        userId: event.data.userId,
      });
    });
  },
);
