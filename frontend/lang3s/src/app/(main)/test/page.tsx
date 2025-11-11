import React from "react";

const Page = () => {
  return (
    <div className="flex flex-1 flex-col gap-2">
      <div className="peer/abc">Test</div>

      <div className="bg-dodger-blue-500 border-2 text-2xl font-semibold peer-hover/abc:border-2">
        Test
      </div>
    </div>
  );
};

export default Page;
