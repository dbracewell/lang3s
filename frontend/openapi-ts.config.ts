const config = [
  {
    input: "http://localhost:8003/openapi.json",
    output: "src/clients/core",
    plugins: [
      "@hey-api/typescript",
      "@hey-api/client-fetch",
      "@tanstack/react-query",
      {
        name: "zod",
        dates: {
          local: true,
        },
      },
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
            if (op.method === "post" && op.path.includes("/search")) {
              return ["query"];
            }
          },
        },
      },
    },
  },
  {
    input: "http://localhost:8003/analytics/openapi.json",
    output: "src/clients/analytics",
    plugins: [
      "@hey-api/typescript",
      "@hey-api/client-fetch",
      "@tanstack/react-query",
      {
        name: "zod",
        dates: {
          local: true,
        },
      },
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

export default config;
