import { caller } from "@/trpc/server";
import React from "react";

const Page = async () => {
  const data = await caller.documents.test({
    type1: "entity",
    type2: "entity",
  });

  return (
    <div>
      {data.map((d, i) => (
        <div key={i}>
          {d.e1 as string} ({d.e1Type}) / {d.e2 as string} ({d.e2Type}):{" "}
          {d.count}
        </div>
      ))}
    </div>
  );
};

export default Page;
