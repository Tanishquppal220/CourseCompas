import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";

interface ChatHeaderProps {
  title?: string;
  onDelete?: () => void;
  isDeleting?: boolean;
}

export function ChatHeader({ title, onDelete, isDeleting }: ChatHeaderProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3 min-w-0">
        <SidebarTrigger />
        <Separator orientation="vertical" className="h-4" />
        <h1 className="text-sm font-medium truncate">{title || "New Chat"}</h1>
      </div>
      {onDelete && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onDelete}
          disabled={isDeleting}
          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 gap-1.5 h-8 px-2.5 cursor-pointer"
          title="Delete this chat"
        >
          <Trash2 className="h-4 w-4" />
          <span className="hidden sm:inline text-xs">Delete Chat</span>
        </Button>
      )}
    </header>
  );
}

