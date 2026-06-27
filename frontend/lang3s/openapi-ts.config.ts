export default [
  {
    input: "http://localhost:8003/openapi.json",
    output: "src/clients/core",
    plugins: [
      "@hey-api/typescript",
      "@hey-api/client-fetch",
      "@tanstack/react-query",
      "zod",
      {
        name: "@hey-api/sdk",
        validator: true,
        operations: {
          strategy: "single",
          containerName: "ApiClient",
        },
      },
    ],
  },
  {
    input: "http://localhost:8003/analytics/openapi.json",
    output: "src/clients/analytics",
    plugins: [
      "@hey-api/typescript",
      "@hey-api/client-fetch",
      "@tanstack/react-query",
      "zod",
      {
        name: "@hey-api/sdk",
        validator: true,
        operations: {
          strategy: "single",
          containerName: "ApiClient",
        },
      },
    ],
    parser: {
      hooks: {
        operations: {
          getKind: (op: any) => {
            if (op.method === "post") {
              return ["query"];
            }
          },
        },
      },
    },
  },
];
