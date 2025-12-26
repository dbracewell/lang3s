import { AccountHeader } from "@/features/auth/ui/views/AccountsPageVIew/AccountHeader";
import { UserApiKeys } from "@/features/auth/ui/views/AccountsPageVIew/UserApiKeys";
import { UserInformation } from "@/features/auth/ui/views/AccountsPageVIew/UserInformation";
import { UserProjects } from "@/features/auth/ui/views/AccountsPageVIew/UserProjects";
import { FullUserInfo } from "@/features/common/types";

export const AccountPageView = ({ user }: { user: FullUserInfo }) => {
  return (
    <div className="flex h-full flex-1 flex-col gap-5 overflow-hidden p-2">
      <AccountHeader user={user} />
      <UserInformation user={user} />
      <div className="scrollable bg-card flex min-h-0 flex-1 flex-col gap-6">
        <UserProjects user={user} />
        <UserApiKeys user={user} />
      </div>
    </div>
  );
};
