import { JobPageView } from "@/features/jobs/ui/views/JobsPageView";
import { getUser, roleHasPermissions } from "@/features/auth/server/actions";
import { redirect } from "next/navigation";

const JobsPage = async () => {
  const user = await getUser();
  const hasPermissions = await roleHasPermissions(user.role, ["jobs:view"]);
  if (!hasPermissions) {
    return redirect("/");
  }
  return <JobPageView />;
};

export default JobsPage;
