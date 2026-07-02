import { client as coreClient } from "@/clients/core/client.gen";
import { client as analyticsClient } from "@/clients/analytics/client.gen";
import { authClient } from "@/lib/auth/auth-client";
import { t3env } from "@/lib/t3env";
import { ApiClient as CoreApiClient } from "@/clients/core";
import { ApiClient as AnalyticsApiClient } from "@/clients/analytics";

coreClient.setConfig({
  baseUrl: t3env.NEXT_PUBLIC_BACKEND_URL,
});
analyticsClient.setConfig({
  baseUrl: `${t3env.NEXT_PUBLIC_BACKEND_URL}/analytics`,
});

coreClient.interceptors.request.use(async (request) => {
  const { data } = await authClient.token();
  if (data?.token) {
    request.headers.set("Authorization", `Bearer ${data.token}`);
  }
  return request;
});

analyticsClient.interceptors.request.use(async (request) => {
  const { data } = await authClient.token();
  if (data?.token) {
    request.headers.set("Authorization", `Bearer ${data.token}`);
  }
  return request;
});

new CoreApiClient({ client: coreClient });
new AnalyticsApiClient({ client: analyticsClient });

export { coreClient, analyticsClient };
