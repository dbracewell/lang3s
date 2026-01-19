import { requireAdmin } from "@/features/auth/server/actions";
import React from "react";
import { Button } from "@/components/ui/button";
import { createRedisClient } from "@/lib/redis";

const AdminPage = async () => {
  const user = await requireAdmin();

  // const onClick = async () => {
  //   await fetch(`http://localhost:8003/topics/finalize`, {
  //     method: "PUT",
  //   })
  //     .then((r) => alert(r.statusText))
  //     .catch((r) => alert(r));
  // };

  const getQueueSize = async () => {
    const client = await createRedisClient();
    const queueSize = client.lLen("doc_queue");
    client.close();
    return queueSize;
  };

  const queueSize = await getQueueSize();

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {user.username}
      {/*<Button onClick={onClick}>Finish Topics</Button>*/}
      {queueSize}
    </div>
  );
};

export default AdminPage;
