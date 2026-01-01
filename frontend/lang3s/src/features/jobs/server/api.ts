import { t3env } from "@/lib/t3env";
import { Permission, roleHasPermissions } from "@/features/auth/permissions";
import { getUserRoleByApiKey } from "@/features/auth/server/actions";
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
