import { env } from "@/env/env";
import { Permission, roleHasPermissions } from "@/features/auth/permissions";
import { getUserByApiKey } from "@/features/auth/server/actions";
import { cache } from "react";
import "server-only";

export const apiKeyHasPermission = cache(
  async (
    apiKey: string | undefined | null,
    permissions: Permission[],
    requireAll: boolean = false,
  ) => {
    if (apiKey == null) {
      return false;
    }
    if (apiKey === env.SYSTEM_KEY) {
      return true;
    }
    const userRole = await getUserByApiKey(apiKey);
    if (userRole == null) {
      return false;
    }
    return roleHasPermissions(userRole, permissions, requireAll);
  },
);
