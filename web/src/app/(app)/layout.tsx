import { Sidebar } from "@/components/app/sidebar";
import { TopBar } from "@/components/app/top-bar";
import { visibleNav } from "@/components/app/nav-config";
import { getContext } from "@/lib/session";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const ctx = await getContext();
  return (
    <div className="flex min-h-dvh">
      <Sidebar sections={visibleNav(ctx)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar ctx={ctx} />
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
