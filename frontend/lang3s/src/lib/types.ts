import { UserRole } from "@/lib/auth/permissions";

export type BasicUserInfo = {
  id: string;
  role: UserRole;
  name: string;
  username: string;
  email: string;
};

export type FullUserInfo = BasicUserInfo & {
  keys?: { id: string; name?: string; key: string }[];
};
