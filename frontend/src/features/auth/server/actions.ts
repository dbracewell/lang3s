"use server";
import { t3env } from "@/lib/t3env";
import { auth } from "@/lib/auth/auth";
import { FullUserInfo } from "@/lib/types";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import {
  AdminAccountSchema,
  AdminAccountSchemaType,
  UserAccountEditSchema,
  UserAccountEditSchemaType,
  UserAccountSchema,
  UserAccountSchemaType,
} from "@/features/auth/schemas";
import { Permission, UserRole } from "@/lib/auth/permissions";
import { RolePermissions } from "@/lib/auth/role-permissions";
import { PAGE_LIMIT } from "@/lib/constants";
import { UserType } from "@/features/auth/ui/components/UserListColumns";
import {
  NAVIGATION_LINKS,
  NavigationGroup,
  NavigationItem,
} from "@/lib/navigation";
import Database from "better-sqlite3";

export const requireAdmin = cache(async () => {
  const user = await getCurrentUser();
  if (user.role !== "admin") {
    redirect("/");
  }
  return user;
});

export const getUserAndNavigation = cache(async () => {
  const user = await getCurrentUser();
  const links: NavigationGroup[] = [];
  for (const section of NAVIGATION_LINKS) {
    const hasSectionPermission =
      section.permissions == null ||
      (await roleHasPermissions(user.role, section.permissions));
    if (hasSectionPermission) {
      const trimmed: NavigationItem[] = [];
      for (const link of section.links) {
        if (link.separator) {
          trimmed.push(link);
        } else {
          const hasLinkPermission =
            link.permissions == null ||
            (await roleHasPermissions(user.role, link.permissions));
          if (hasLinkPermission) {
            trimmed.push(link);
          }
        }
      }
      section.links = trimmed;
      links.push(section);
    }
  }
  return {
    user,
    navigation: links,
  };
});

export const getCurrentUser = cache(async (): Promise<FullUserInfo> => {
  const headersList = await headers();
  const session = await auth.api.getSession({
    headers: headersList,
  });
  if (!session?.user || session.user.role == null) {
    redirect("/sign-in");
  }
  const { apiKeys } = await auth.api.listApiKeys({
    headers: headersList,
  });
  return {
    id: session.user.id,
    username: session.user.username as string,
    role: session.user.role as UserRole,
    name: session.user.name,
    email: session.user.email as string,
    keys: [
      ...apiKeys.values().map((key) => ({
        id: key.id,
        name: key.name ?? undefined,
        key: key.id,
      })),
    ],
  };
});

export const removeUser = async (userId: string) => {
  await requireAdmin();
  const result = await auth.api.removeUser({
    headers: await headers(),
    body: {
      userId: userId,
    },
  });
  return result.success;
};

export const listUsers = async (page: number) => {
  await requireAdmin();
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
    username: (u as { username?: string }).username ?? "",
    banned: !!u.banned,
    role: u.role as UserRole,
  })) as UserType[];
};

export const createUser = async (user: UserAccountSchemaType) => {
  await requireAdmin();
  const parsed = UserAccountSchema.safeParse(user);
  if (!parsed.success) {
    return {
      code: 400,
      message: "Username already taken",
      path: "username",
    };
  }

  const headersList = await headers();

  const usernameResult = await auth.api.isUsernameAvailable({
    headers: headersList,
    body: {
      username: parsed.data.username,
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
        ...parsed.data,
        data: { username: parsed.data.username },
      },
    });
    return { code: 200, userId: user.id };
  } catch (error) {
    if (error instanceof Error) {
      return { code: 400, message: error.message, path: "email" };
    }
    return { code: 500, message: "Something went wrong" };
  }
};

export const updateUser = async (user: UserAccountEditSchemaType) => {
  await requireAdmin();
  const parsed = UserAccountEditSchema.safeParse(user);
  if (!parsed.success) {
    return {
      code: 400,
    };
  }
  return await auth.api.adminUpdateUser({
    headers: await headers(),
    body: {
      userId: parsed.data.userId,
      data: {
        role: parsed.data.role,
        banned: !parsed.data.isActive,
      },
    },
  });
};

export const getUserCount = async () => {
  const db = new Database(t3env.DATABASE_URL, { readonly: true });
  const row = db.prepare("SELECT COUNT(*) AS count FROM user").get() as {
    count: number;
  };
  return row.count;
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

  await auth.api.signUpEmail({
    body: {
      username: safeValues.data.username,
      name: safeValues.data.name,
      email: safeValues.data.email,
      password: safeValues.data.password,
      displayUsername: safeValues.data.username,
    },
    query: {
      adminKey: values.passphrase,
    },
  });
  return { status: 200 };
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
