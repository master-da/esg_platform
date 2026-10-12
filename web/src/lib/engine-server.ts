import "server-only";
import { createClient } from "@/lib/supabase/server";
import { ENGINE_URL, parseEngineResponse } from "@/lib/engine-shared";

/** Call the engine from a Server Component as the signed-in user. */
export async function engineGet<T>(path: string): Promise<T> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const res = await fetch(`${ENGINE_URL}${path}`, {
    headers: { Authorization: `Bearer ${data.session?.access_token ?? ""}` },
    cache: "no-store",
  });
  return parseEngineResponse<T>(res);
}
