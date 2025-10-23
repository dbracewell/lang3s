import { createAccessControl } from "better-auth/plugins/access";
import { defaultStatements, adminAc } from "better-auth/plugins/admin/access";

const statement = {
  ...defaultStatements,
  project: ["create", "share", "update", "delete", "view"],
  data: ["load", "update"],
  model: ["create", "delete", "export"],
} as const;

export const ac = createAccessControl(statement);

export const user = ac.newRole({
  project: ["view"],
});

export const admin = ac.newRole({
  project: ["create", "share", "update", "delete", "view"],
  data: ["load", "update"],
  model: ["create", "delete", "export"],
  ...adminAc.statements,
});

export const analyst = ac.newRole({
  project: ["create", "share", "update", "delete", "view"],
});

export const modeller = ac.newRole({
  project: ["create", "share", "update", "delete", "view"],
  data: ["update"],
  model: ["create", "delete"],
});

export const dataLoader = ac.newRole({
  data: ["load"],
});
