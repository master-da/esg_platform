"use client";

import { createClient } from "@/lib/supabase/client";
import { ENGINE_URL, parseEngineResponse } from "@/lib/engine-shared";

async function token(): Promise<string> {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token ?? "";
}

/** Call the engine from the browser as the signed-in user. */
export async function engine<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...rest,
    headers: {
      Authorization: `Bearer ${await token()}`,
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  return parseEngineResponse<T>(res);
}

/** Download a file returned by the engine and save it with the server-provided name. */
export async function engineDownload(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${ENGINE_URL}${path}`, { headers: { Authorization: `Bearer ${await token()}` } });
  const blob = await parseEngineResponse<Blob>(res);
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const name = match ? decodeURIComponent(match[1]) : fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
