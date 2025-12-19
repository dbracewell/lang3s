"use server";
import { db } from "@/lib/db";
import { apikey as ApiKeyTable, user as UserTable } from "@/lib/db/schema";
import { env } from "@/lib/env/env";
import { auth } from "@/lib/auth/auth";
import { logAndRethrow } from "@/lib/utils/try-catch";
import { UserRole } from "@/features/auth/permissions";
import {
  AdminAccountSchema,
  AdminAccountSchemaType,
} from "@/features/common/schemas";
import { BasicUserInfo } from "@/features/common/types";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

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
  };
});

export const getUserByApiKey = cache(async (apiKey: string) => {
  const [user] = await logAndRethrow(
    db
      .select({
        role: UserTable.role,
      })
      .from(ApiKeyTable)
      .innerJoin(UserTable, eq(ApiKeyTable.userId, UserTable.id))
      .where(eq(ApiKeyTable.key, apiKey)),
  );
  return user.role as UserRole | null;
});

export const getUserCount = async () => {
  return await db.$count(UserTable);
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
  if (safeValues.data.passphrase != env.ADMIN_PASSPHRASE) {
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
  return await logAndRethrow(
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
