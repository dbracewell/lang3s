"use server";
import { db } from "@/lib/db";
import { apikey as ApiKeyTable, user as UserTable } from "@/lib/db/schema";
import { t3env } from "@/lib/t3env";
import { auth } from "@/lib/auth/auth";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { BasicUserInfo } from "@/features/common/types";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import {
  AdminAccountSchema,
  AdminAccountSchemaType,
} from "@/features/auth/schemas";
import { Permission, UserRole } from "@/lib/auth/permissions";
import { RolePermissions } from "@/lib/auth/role-permissions";
import { TRPCError } from "@trpc/server";

export const requireAdmin = cache(async () => {
  const user = await getUser();
  if (user.role !== "admin") {
    redirect("/");
  }
  return user;
});

export const getUser = cache(async (): Promise<BasicUserInfo> => {
  const session = await auth.api.getSession({
    headers: await headers(),
  });
  if (!session?.user || session.user.role == null) {
    redirect("/sign-in");
  }
  return {
    id: session.user.id,
    username: session.user.username as string,
    role: session.user.role as UserRole,
    name: session.user.name,
  };
});

export const getUserRoleByApiKey = cache(async (apiKey: string) => {
  const user = await getUserByApiKey(apiKey);
  return user ? (user.role as UserRole | null) : null;
});

export const getUserByApiKey = cache(async (apiKey: string) => {
  const [user] = await logAndRethrow(() =>
    db
      .select()
      .from(ApiKeyTable)
      .innerJoin(UserTable, eq(ApiKeyTable.userId, UserTable.id))
      .where(eq(ApiKeyTable.key, apiKey)),
  );
  return user?.user as BasicUserInfo;
});

export const getAdminAccount = cache(async () => {
  const [admin] = await logAndRethrow(() =>
    db.select().from(UserTable).where(eq(UserTable.role, "admin")),
  );
  if (!admin) {
    throw new Error("Admin account not found");
  }
  return admin as BasicUserInfo;
});

export const getUserCount = async () => {
  return db.$count(UserTable);
};

export const createAdminAccount = async (values: AdminAccountSchemaType) => {
  const userCount = await getUserCount();
  if (userCount > 0) {
    return;
  }
  const safeValues = AdminAccountSchema.safeParse(values);
  if (!safeValues.success) {
    return {
      status: 400,
    };
  }
  if (safeValues.data.passphrase != t3env.ADMIN_PASSPHRASE) {
    return {
      status: 401,
    };
  }

  try {
    const res = await auth.api.signUpEmail({
      body: {
        username: safeValues.data.username,
        name: safeValues.data.name,
        email: safeValues.data.email,
        password: safeValues.data.password,
        displayUsername: safeValues.data.username,
      },
    });
    await db
      .update(UserTable)
      .set({
        role: "admin",
      })
      .where(eq(UserTable.id, res.user.id));
    return { status: 200 };
  } catch (error) {
    return {
      status: 500,
    };
  }
};

export const getUserApiKeys = async (userId: string) => {
  return await logAndRethrow(() =>
    db
      .select({
        id: ApiKeyTable.id,
        name: ApiKeyTable.name,
        key: ApiKeyTable.key,
      })
      .from(ApiKeyTable)
      .where(eq(ApiKeyTable.userId, userId)),
  );
};

export const roleHasPermissions = cache(
  async (
    role: UserRole,
    permissions: Permission[],
    requireAll: boolean = false,
  ) => {
    if (role === "admin") return true;
    const pSet = new Set(permissions);
    const rSet = new Set(RolePermissions[role]);
    if (rSet.size === 0) return false;
    const intersection = pSet.intersection(rSet);
    if (requireAll) {
      return pSet.size === intersection.size;
    }
    return intersection.size > 0;
  },
);

export const requirePermissions = cache(
  async (
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
      const hasUserPermissions = await roleHasPermissions(
        user.role,
        permissions,
        requireAll,
      );
      if (!hasUserPermissions) {
        throw new TRPCError({ code: "UNAUTHORIZED" });
      }
    }
  },
);

export const apiKeyHasPermission = cache(
  async (
    apiKey: string | undefined | null,
    permissions: Permission[],
    requireAll: boolean = false,
  ) => {
    if (apiKey == null) {
      return false;
    }
    if (apiKey === t3env.SYSTEM_KEY) {
      return true;
    }
    const userRole = await getUserRoleByApiKey(apiKey);
    if (userRole == null) {
      return false;
    }
    return roleHasPermissions(userRole, permissions, requireAll);
  },
);

export const isSystemApiKey = async (apiKey: string | undefined) => {
  return !!apiKey && apiKey === t3env.SYSTEM_KEY;
};
