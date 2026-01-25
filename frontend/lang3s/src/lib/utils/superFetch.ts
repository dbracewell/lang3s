export const postJson = async <T>(url: string, body?: Record<string, any>) => {
  return fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (response: Response) => {
    if (response.ok) {
      const json = await response.json();
      return json as T;
    }
  });
};
