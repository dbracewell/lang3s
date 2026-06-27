import { client as _coreClient } from "@/clients/core/client.gen";
import {
  ApiClient as CoreApiClient,
  ErrorDetail,
  HttpValidationError,
} from "@/clients/core";
import { client as _analyticsClient } from "@/clients/analytics/client.gen";
import { ApiClient as AnalyticsApiClient } from "@/clients/analytics";

_coreClient.setConfig({
  baseUrl: "http://localhost:3000/api/backend",
});
_analyticsClient.setConfig({
  baseUrl: "http://localhost:3000/api/backend/analytics",
});

export const coreClient = _coreClient;
export const analyticsClient = _analyticsClient;

export const coreApi = new CoreApiClient({ client: coreClient });
export const analyticsApi = new AnalyticsApiClient({ client: analyticsClient });

export const handleResult = <T>({
  data,
  error,
}: {
  data: T | undefined;
  error: ErrorDetail | HttpValidationError | undefined;
}) => {
  if (error != null) {
    if (typeof error.detail === "string") {
      throw Error(error.detail);
    }
    throw Error("Validation Error");
  }
  if (data == null) {
    throw Error("Internal Server Error");
  }
  return data;
};
