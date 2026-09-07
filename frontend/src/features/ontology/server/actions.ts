"use server";

import { getCurrentUser } from "@/features/auth/server/actions";
import { auth } from "@/lib/auth/auth";
import { client as coreClient } from "@/clients/core/client.gen";
import { ApiClient as CoreApiClient, Job } from "@/clients/core";
import { client as analyticsClient } from "@/clients/analytics/client.gen";
import { ApiClient as AnalyticsApiClient } from "@/clients/analytics";
import { t3env } from "@/lib/t3env";
import { headers } from "next/headers";

export const updateAnalytics = async () => {
  const user = await getCurrentUser();
  const hasPermission = await auth.api.userHasPermission({
    body: {
      userId: user.id,
      role: user.role,
      permissions: {
        ontology: ["edit"],
        job: ["create"],
      },
    },
  });
  if (hasPermission.error || !hasPermission.success) {
    throw new Error("Unauthorized");
  }
  const { token: jwtToken } = await auth.api.getToken({
    headers: await headers(),
  });
  if (!jwtToken) {
    throw new Error("Unauthorized");
  }

  coreClient.setConfig({
    baseUrl: t3env.NEXT_PUBLIC_BACKEND_URL,
    headers: {
      Authorization: `Bearer ${jwtToken}`,
    },
  });
  const coreApi = new CoreApiClient({ client: coreClient });
  analyticsClient.setConfig({
    baseUrl: `${t3env.NEXT_PUBLIC_BACKEND_URL}/analytics`,
    headers: {
      Authorization: `Bearer ${jwtToken}`,
    },
  });
  const analyticsApi = new AnalyticsApiClient({ client: analyticsClient });

  let numberRunning: number;
  try {
    const { data } = await coreApi.jobsGetRunningCount({
      throwOnError: true,
      path: { job_type: "analyticsupdate" },
    });
    numberRunning = data;
  } catch (error) {
    console.error("Get Running Job Count", error);
    throw error;
  }

  if (numberRunning > 0) {
    throw new Error("Running Count");
  }

  let job: Job;
  try {
    const { data } = await coreApi.jobsCreateJob({
      throwOnError: true,
      body: {
        status: "running",
        name: `AnalyticsUpdate (${user.username}) ${new Date().toISOString()}`,
        type_: "analyticsupdate",
        total: 1,
      },
    });
    job = data;
  } catch (error) {
    console.error("Creat Job", error);
    throw error;
  }

  try {
    await analyticsApi.analysisUpdateStats({
      throwOnError: true,
      body: job,
    });
  } catch (error) {
    await coreApi.jobsDeleteJob({
      path: {
        job_id: job.id,
      },
    });
    console.error("Update Stats", error);
    throw error;
  }
  return job;
};
