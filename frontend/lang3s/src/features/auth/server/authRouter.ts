import { db } from "@/lib/db";
import { apikey as ApiKeyTable, user as UserTable } from "@/lib/db/schema";
import { auth } from "@/lib/auth/auth";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { UserType } from "@/features/auth/ui/components/UserListColumns";
import { Permissions, UserRole } from "@/lib/auth/permissions";
import {
  getUserApiKeys,
  requirePermissions,
  roleHasPermissions,
} from "@/features/auth/server/actions";
import {
  adminProcedure,
  createTRPCRouter,
  protectedProcedure,
} from "@/lib/trpc/init";
import { and, eq } from "drizzle-orm";
import { headers } from "next/headers";
import z from "zod";
import { UserAccountSchema } from "@/features/auth/schemas";
import { jsonAgg, jsonBuildObject } from "@/lib/db/helpers/json";
import {
  NAVIGATION_LINKS,
  NavigationGroup,
  NavigationItem,
} from "@/features/common/navigation";
import { PAGE_LIMIT } from "@/features/common/constants";

export const authRouter = createTRPCRouter({
  hasPermission: protectedProcedure
    .input(
      z.object({
        permissions: z.array(z.enum(Permissions)),
        requireAll: z.boolean().optional(),
      }),
    )
    .query(async ({ input, ctx }) => {
      const user = ctx.user;
      const { permissions, requireAll } = input;
      return await roleHasPermissions(user.role, permissions, requireAll);
    }),
  getNavigation: protectedProcedure.query(async ({ ctx }) => {
    const {
      user: { role },
    } = ctx;
    const links: NavigationGroup[] = [];
    for (const section of NAVIGATION_LINKS) {
      const hasSectionPermission =
        section.permissions == null ||
        (await roleHasPermissions(role, section.permissions));
      if (hasSectionPermission) {
        const trimmed: NavigationItem[] = [];
        for (const link of section.links) {
          if (link.separator) {
            trimmed.push(link);
          } else {
            const hasLinkPermission =
              link.permissions == null ||
              (await roleHasPermissions(role, link.permissions));
            if (hasLinkPermission) {
              trimmed.push(link);
            }
          }
        }
        section.links = trimmed;
        links.push(section);
      }
    }
    return links;
  }),

  getUsers: adminProcedure
    .input(
      z.object({
        page: z.int(),
      }),
    )
    .query(async ({ input }) => {
      const { page } = input;
      const actualPage = Number.isNaN(page) || page < 1 ? 1 : page;
      const { users } = await auth.api.listUsers({
        headers: await headers(),
        query: {
          limit: PAGE_LIMIT,
          offset: actualPage - 1,
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
      await logAndRethrow(async () =>
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
          //@ts-ignore
          body: {
            ...input,
            data: { username: input.username },
          },
        });
        return { code: 200, userId: user.id };
      } catch (error) {
        console.error(error);
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
    await requirePermissions(user, undefined, ["data:load"]);
    const headersList = await headers();

    const data = await logAndRethrow(() => {
      const randId = crypto.randomUUID().slice(0, 4);
      return auth.api.createApiKey({
        headers: headersList,
        body: {
          name: `${user.username}-api-key-${randId}`,
          userId: user.id,
          prefix: "lang3s",
        },
      });
    });
    return data.key;
  }),

  deleteApiKey: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const { user } = ctx;
      const where = [eq(ApiKeyTable.id, input.id)];
      if (user.role !== "admin") {
        where.push(eq(ApiKeyTable.userId, user.id));
      }
      const [result] = await logAndRethrow(() =>
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
        keys: jsonAgg(
          jsonBuildObject({
            id: ApiKeyTable.id,
            name: ApiKeyTable.name,
            key: ApiKeyTable.key,
          }),
        ).as("keys"),
      })
      .from(ApiKeyTable)
      .groupBy((t) => t.userId)
      .as("apiKeys");

    const [u] = await logAndRethrow(() =>
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
      username: u.username ?? u.email,
      role: u.role as UserRole,
      keys: (u.keys ?? []).map((k) => ({
        id: k.id,
        name: k.name!,
        key: k.key,
      })),
    };
  }),
});
