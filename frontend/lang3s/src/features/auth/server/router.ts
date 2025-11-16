import { db } from "@/db";
import { apikey as ApiKeyTable, user as UserTable } from "@/db/schema";
import { auth } from "@/lib/auth";
import { logAndRethrow } from "@/lib/try-catch";
import { UserType } from "@/features/admin/ui/views/AdminUsersPageView/columns";
import { UserRole } from "@/features/auth/permissions";
import { getUserApiKeys } from "@/features/auth/server/actions";
import { UserAccountSchema } from "@/features/common/schemas";
import {
  adminProcedure,
  createTRPCRouter,
  protectedProcedure,
  requirePermissions,
} from "@/trpc/init";
import { and, eq, sql } from "drizzle-orm";
import { headers } from "next/headers";
import z from "zod";

export const authRouter = createTRPCRouter({
  getCurrentUser: protectedProcedure.query(async ({ ctx }) => {
    const { user } = ctx;
    return user;
  }),

  getUsers: adminProcedure.query(async () => {
    const { users } = await auth.api.listUsers({
      headers: await headers(),
      query: {
        limit: 100,
        offset: 0,
        sortBy: "name",
        filterField: "role",
        filterValue: "admin",
        filterOperator: "ne",
      },
    });

    return users.map((u) => ({
      ...u,
      role: u.role as UserRole,
    })) as UserType[];
  }),

  updateUser: adminProcedure
    .input(
      z.object({
        userId: z.string(),
        role: z.string(),
        isActive: z.boolean(),
      }),
    )
    .mutation(async ({ input }) => {
      await logAndRethrow(
        auth.api.adminUpdateUser({
          headers: await headers(),
          body: {
            userId: input.userId,
            data: {
              role: input.role,
              banned: !input.isActive,
            },
          },
        }),
      );
      return true;
    }),

  createUser: adminProcedure
    .input(UserAccountSchema)
    .mutation(async ({ input }) => {
      const headersList = await headers();

      const usernameResult = await auth.api.isUsernameAvailable({
        headers: headersList,
        body: {
          username: input.username,
        },
      });

      if (!usernameResult.available) {
        return {
          code: 400,
          message: "Username already taken",
          path: "username",
        };
      }

      try {
        const { user } = await auth.api.createUser({
          headers: headersList,
          body: {
            ...input,
            data: { username: input.username },
          },
        });
        return { code: 200, userId: user.id };
      } catch (error) {
        if (error instanceof Error) {
          return { code: 400, message: error.message, path: "email" };
        }
        return { code: 500, message: "Something went wrong" };
      }
    }),

  deleteUser: adminProcedure
    .input(z.object({ userId: z.string().min(1) }))
    .mutation(async ({ input }) => {
      const result = await auth.api.removeUser({
        headers: await headers(),
        body: {
          userId: input.userId,
        },
      });
      return result.success;
    }),

  createApiKey: protectedProcedure.mutation(async ({ ctx }) => {
    const { user } = ctx;
    await requirePermissions(user, undefined, ["data:load", "data:update"]);
    const headersList = await headers();

    try {
      const randId = crypto.randomUUID().slice(0, 4);
      const data = await auth.api.createApiKey({
        headers: headersList,
        body: {
          name: `${user.username}-api-key-${randId}`,
          userId: user.id,
          prefix: "lang3s",
        },
      });
      return data.key;
    } catch (error) {
      console.error(error);
      throw error as Error;
    }
  }),

  deleteApiKey: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const { user } = ctx;
      const where = [eq(ApiKeyTable.id, input.id)];
      if (user.role !== "admin") {
        where.push(eq(ApiKeyTable.userId, user.id));
      }
      const [result] = await logAndRethrow(
        db
          .delete(ApiKeyTable)
          .where(and(...where))
          .returning(),
      );
      return result.id;
    }),

  getApiKeys: protectedProcedure.query(async ({ ctx }) => {
    const { user } = ctx;
    return await getUserApiKeys(user.id);
  }),

  getAccount: protectedProcedure.query(async ({ ctx }) => {
    const { user } = ctx;

    const apiKeys = db
      .select({
        userId: ApiKeyTable.userId,
        keys: sql<
          {
            id: string;
            name: string;
            key: string;
          }[]
        >`json_agg(json_build_object('id', ${ApiKeyTable.id}, 'name',${ApiKeyTable.name}, 'key', ${ApiKeyTable.key}))`.as(
          "key",
        ),
      })
      .from(ApiKeyTable)
      .groupBy((t) => t.userId)
      .as("apiKeys");

    const [u] = await logAndRethrow(
      db
        .select({
          id: UserTable.id,
          name: UserTable.name,
          email: UserTable.email,
          username: UserTable.username,
          role: UserTable.role,
          keys: apiKeys.keys,
        })
        .from(UserTable)
        .leftJoin(apiKeys, eq(UserTable.id, apiKeys.userId))
        .where(eq(UserTable.id, user.id)),
    );

    return {
      ...u,
      role: u.role as UserRole,
      keys: (u.keys ?? []).map((k) => ({
        id: k.id,
        name: k.name!,
        key: k.key,
      })),
    };
  }),
});
