export const ENGINE_URL = process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";

export class EngineError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type FastApiDetail = string | { loc?: (string | number)[]; msg: string }[] | Record<string, unknown>;

export function describeError(detail: FastApiDetail | undefined, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`.replace(/^: /, "")).join("; ");
  }
  if (typeof detail === "object" && "message" in detail) return String(detail.message);
  return fallback;
}

export async function parseEngineResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: FastApiDetail | undefined;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* non-JSON error body */
    }
    throw new EngineError(res.status, describeError(detail, `Request failed (${res.status})`));
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}
