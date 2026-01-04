import { getUserCount, requireAdmin } from "@/features/auth/server/actions";
import { caller } from "@/lib/trpc/server";
import { UserList } from "@/features/auth/ui/components/UserList";
import { PAGE_LIMIT } from "@/features/common/constants";

const AdminUsersPage = async (props: PageProps<"/admin/users">) => {
  await requireAdmin();
  const query = await props.searchParams;
  const page = (query?.page as string) ?? undefined;
  const parsedPage =
    page == null || Number.isNaN(Number(page)) ? 1 : Number(page);
  const [data, totalUsers] = await Promise.all([
    caller.auth.getUsers({
      page: parsedPage,
    }),
    getUserCount(),
  ]);
  return (
    <UserList
      users={data}
      page={parsedPage}
      totalPages={Math.ceil(totalUsers / PAGE_LIMIT)}
    />
  );
};

export default AdminUsersPage;
