const superFetchJson = async <T>(
  method: "POST" | "PUT",
  url: string,
  body?: Record<string, any>,
) => {
  return fetch(url, {
    method: method,
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (response: Response) => {
    if (response.ok) {
      const json = await response.json();
      return json as T;
    } else {
      const errorData = await response.json().catch(() => ({}));
      console.error(errorData);
      throw new Error(
        JSON.stringify(errorData) || "Network response was not ok",
      );
    }
  });
};

const superGet = async <T>(url: string) => {
  return fetch(url).then(async (response: Response) => {
    if (response.ok) {
      const json = await response.json();
      return json as T;
    } else {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        JSON.stringify(errorData) || "Network response was not ok",
      );
    }
  });
};

export const getJson = async <T>(url: string) => {
  return superGet<T>(url);
};

export const postJson = async <T>(url: string, body?: Record<string, any>) => {
  return superFetchJson<T>("POST", url, body);
};

export const putJson = async <T>(url: string, body?: Record<string, any>) => {
  return superFetchJson<T>("PUT", url, body);
};
