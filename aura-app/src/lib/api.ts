export async function api<T = Record<string, unknown>>(
  route: string,
  data?: unknown,
): Promise<T> {
  const response = await fetch(
    "/api/" + route,
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "AURA is unavailable");
  return result;
}
