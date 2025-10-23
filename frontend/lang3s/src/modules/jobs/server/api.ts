import "server-only";

export const isValidApiKey = async (apiKey: string) => {
  if (apiKey === process.env.JOBS_API_KEY!) {
    return true;
  }

  return false;
};
