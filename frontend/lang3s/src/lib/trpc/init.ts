import { t3env } from "@/lib/t3env";
import { auth } from "@/lib/auth/auth";
import {
  Permission,
  roleHasPermissions,
  UserRole,
} from "@/features/auth/permissions";
import { apiKeyHasPermission } from "@/features/jobs/server/api";
import { BasicUserInfo } from "@/features/common/types";
import { initTRPC, TRPCError } from "@trpc/server";
import { headers } from "next/headers";
import { cache } from "react";
import superjson from "superjson";

const API_KEY_HEADER = "lang3s-api-key";

export const createTRPCContext = cache(async () => {
  const headerList = await headers();
  const session = await auth.api.getSession({ headers: headerList });
  const apiKey = headerList.get(API_KEY_HEADER) ?? undefined;

  if (session == null) {
    return {
      user: undefined,
      apiKey,
    };
  }

  if (session.user.banned) {
    return {
      user: undefined,
      apiKey,
    };
  }

  return {
    user: {
      id: session.user.id,
      role: session.user.role as UserRole,
      username: session.user.username as string,
    } as BasicUserInfo,
    apiKey,
  };
});

type Context = Awaited<ReturnType<typeof createTRPCContext>>;

const t = initTRPC.context<Context>().create({
  transformer: superjson,
});

const protectedMiddleware = t.middleware(async ({ next, ctx }) => {
  const { user } = ctx;

  if (!user?.id) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }

  return next({
    ctx: {
      user: user,
    },
  });
});

const adminMiddleware = t.middleware(async ({ next, ctx }) => {
  const { user } = ctx;

  if (!user?.id || user.role !== "admin") {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }

  return next({
    ctx: {
      user: user,
    },
  });
});

export const apiMiddleWare = t.middleware(async ({ next, ctx }) => {
  const { user, apiKey } = ctx;

  if (user == null && apiKey == null) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }
  return next({
    ctx: {
      ...ctx,
    },
  });
});

export const requirePermissions = async (
  user: BasicUserInfo | undefined,
  apiKey: string | undefined,
  permissions: Permission[],
  requireAll: boolean = false,
) => {
  const hasApiPermission = await apiKeyHasPermission(
    apiKey,
    permissions,
    requireAll,
  );
  if (!hasApiPermission) {
    if (!user) {
      throw new TRPCError({ code: "UNAUTHORIZED" });
    }
    const hasUserPermissions = roleHasPermissions(
      user.role,
      permissions,
      requireAll,
    );
    if (!hasUserPermissions) {
      throw new TRPCError({ code: "UNAUTHORIZED" });
    }
  }
};

export const isSystemApiKey = (apiKey: string | undefined) => {
  return !!apiKey && apiKey === t3env.SYSTEM_KEY;
};

// Base router and procedure helpers
export const createTRPCRouter = t.router;
export const createCallerFactory = t.createCallerFactory;
export const baseProcedure = t.procedure;
export const protectedProcedure = t.procedure.use(protectedMiddleware);
export const adminProcedure = t.procedure.use(adminMiddleware);
export const apiProcedure = t.procedure.use(apiMiddleWare);
