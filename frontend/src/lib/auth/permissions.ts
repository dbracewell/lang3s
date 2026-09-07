import { createAccessControl } from "better-auth/plugins/access";
import {
  adminAc,
  defaultStatements,
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
  "metadata:edit",
  "ontology:edit",
] as const;

export type UserRole = (typeof UserRoles)[number];
export type Permission = (typeof Permissions)[number];

const permissionsByAsset = {
  ...defaultStatements,
  project: ["create", "share", "update", "delete"],
  apiKey: ["create", "delete"],
  job: ["list", "get", "delete", "create"],
  metadata: ["edit"],
  ontology: ["edit"],
};

export const ac = createAccessControl(permissionsByAsset);

export const user = ac.newRole({
  ...userAc.statements,
});

export const admin = ac.newRole({
  project: ["create", "share", "update", "delete"],
  apiKey: ["create", "delete"],
  job: ["list", "get", "delete", "create"],
  metadata: ["edit"],
  ontology: ["edit"],
  ...adminAc.statements,
});

export const analyst = ac.newRole({
  project: ["create", "share", "update", "delete"],
  ...userAc.statements,
});

export const modeller = ac.newRole({
  project: ["create", "share", "update", "delete"],
  apiKey: ["create", "delete"],
  job: ["list", "get", "delete", "create"],
  metadata: ["edit"],
  ontology: ["edit"],
  ...userAc.statements,
});

export const dataLoader = ac.newRole({
  project: ["create", "share", "update", "delete"],
  apiKey: ["create", "delete"],
  job: ["list", "get", "delete", "create"],
  ...userAc.statements,
});
