import "server-only";
import { Permission, Permissions, UserRole } from "@/lib/auth/permissions";

export const RolePermissions: Record<UserRole, Permission[]> = {
  admin: [...Permissions],
  user: ["project:view"],
  analyst: [
    "project:create",
    "project:share",
    "project:update",
    "project:delete",
    "project:view",
  ],
  modeller: [
    "project:create",
    "project:share",
    "project:update",
    "project:delete",
    "project:view",
    "model:create",
    "model:delete",
    "model:export",
    "jobs:view",
    "jobs:create",
    "jobs:delete",
    "ontology:edit",
    "metadata:edit",
  ],
  dataLoader: [
    "project:create",
    "project:share",
    "project:update",
    "project:delete",
    "project:view",
    "data:load",
    "data:update",
    "jobs:view",
    "jobs:create",
    "jobs:delete",
    "ontology:edit",
    "metadata:edit",
  ],
};
