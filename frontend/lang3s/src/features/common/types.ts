import { UserRole } from "@/features/auth/permissions";

export type BasicUserInfo = {
  id: string;
  role: UserRole;
  username: string;
};

export type FullUserInfo = BasicUserInfo & {
  name: string;
  email: string;
  keys?: { id: string; name?: string; key: string }[];
};
