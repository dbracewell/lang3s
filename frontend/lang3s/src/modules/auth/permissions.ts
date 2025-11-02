import { createAccessControl } from "better-auth/plugins/access";
import {
  defaultStatements,
  adminAc,
  userAc,
} from "better-auth/plugins/admin/access";

export const UserRoles = [
  "admin",
  "user",
  "analyst",
  "modeller",
  "dataLoader",
] as const;

export const Permissions = [
  "user:create",
  "user:list",
  "user:set-role",
  "user:ban",
  "user:impersonate",
  "user:delete",
  "user:set-password",
  "user:get",
  "user:update",
  "session:list",
  "session:revoke",
  "session:delete",
  "project:create",
  "project:share",
  "project:update",
  "project:delete",
  "project:view",
  "data:load",
  "data:update",
  "model:create",
  "model:delete",
  "model:export",
  "jobs:view",
  "jobs:delete",
  "jobs:create",
] as const;

export type UserRole = (typeof UserRoles)[number];
export type Permission = (typeof Permissions)[number];

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
  ],
};

const permissionsByAsset = {
  ...defaultStatements,
};
export const ac = createAccessControl(permissionsByAsset);

export const user = ac.newRole({
  ...userAc.statements,
});
export const admin = ac.newRole({
  ...adminAc.statements,
});

export const analyst = ac.newRole({
  ...userAc.statements,
});

export const modeller = ac.newRole({
  ...userAc.statements,
});

export const dataLoader = ac.newRole({
  ...userAc.statements,
});

export const UserRoleDescriptions = {
  user: "Regular user able to view data and take notes",
  admin: "Admin user has complete control over the system",
  dataLoader: "Has the ability to upload data to the system",
  analyst: "Has the ability to create and share custom projects",
  modeller: "Has the ability to create and delete custom models",
} as const;

export const roleHasPermissions = (
  role: UserRole,
  permissions: Permission[],
  requireAll: boolean = false,
) => {
  if (role === "admin") return true;
  const pSet = new Set(permissions);
  const rSet = new Set(RolePermissions[role]);
  const intersection = pSet.intersection(rSet);
  if (requireAll) {
    return pSet.size === intersection.size;
  }
  return intersection.size > 0;
};
