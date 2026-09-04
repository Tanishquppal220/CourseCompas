import { SidebarTrigger } from "@/components/ui/sidebar";

export function ChatHeader() {
  return (
    <header className="flex h-14 items-center border-b px-4">
      <SidebarTrigger />

      <div className="ml-3">
        <h1 className="text-sm font-medium">New Chat</h1>
      </div>
    </header>
  );
}
