import React, { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { GraduationCap } from "lucide-react";

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background font-sans">
        <AppSidebar 
          currentSessionId={sessionId} 
          onSessionChange={setSessionId} 
        />
        <main className="flex-1 flex flex-col h-screen overflow-hidden">
          {/* Mobile/Compact Header */}
          <header className="h-14 border-b flex items-center px-4 gap-4 bg-background shrink-0">
            <SidebarTrigger />
            <div className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-primary" />
              <span className="font-heading font-medium tracking-tight">Chat</span>
            </div>
          </header>
          
          {/* Chat Area - takes full remaining height */}
          <div className="flex-1 overflow-hidden bg-background">
            <div className="h-full w-full max-w-4xl mx-auto flex flex-col">
              <ChatInterface 
                className="h-full border-none rounded-none" 
                sessionId={sessionId}
                onSessionChange={setSessionId}
              />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
}
