import { Card, CardContent } from "@/components/ui/card";
import { AccountHeader } from "@/features/account/ui/views/AccountsPageVIew/AccountHeader";
import { UserApiKeys } from "@/features/account/ui/views/AccountsPageVIew/UserApiKeys";
import { UserInformation } from "@/features/account/ui/views/AccountsPageVIew/UserInformation";
import { UserProjects } from "@/features/account/ui/views/AccountsPageVIew/UserProjects";
import { FullUserInfo } from "@/features/common/types";

export const AccountPageView = ({ user }: { user: FullUserInfo }) => {
  return (
    <Card className="h-full min-h-0 flex-1">
      <AccountHeader user={user} />
      <CardContent className="scrollable flex flex-col gap-2">
        <UserInformation user={user} />
        <UserProjects user={user} />
        <UserApiKeys user={user} />
      </CardContent>
    </Card>
  );
};
