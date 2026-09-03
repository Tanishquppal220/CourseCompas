import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { 
  Sidebar, 
  SidebarContent, 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarGroupLabel, 
  SidebarHeader,
  SidebarMenu, 
  SidebarMenuItem, 
  SidebarMenuButton 
} from "@/components/ui/sidebar";
import { MessageSquare, LayoutDashboard, Settings, Plus, GraduationCap, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface ChatSession {
  id: string;
  title: string;
  updated_at: string;
}

interface AppSidebarProps {
  currentSessionId?: string | null;
  onSessionChange?: (id: string | null) => void;
}

export function AppSidebar({ currentSessionId, onSessionChange }: AppSidebarProps) {
  const { user, token, logout } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  useEffect(() => {
    if (token) {
      const fetchSessions = async () => {
        try {
          const response = await fetch('/api/chat/sessions', {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (response.ok) {
            const data = await response.json();
            setSessions(data);
          }
        } catch (error) {
          console.error("Failed to fetch sessions:", error);
        }
      };
      fetchSessions();
    }
  }, [token, currentSessionId]); // Refetch when current session changes (might have new title)

  return (
    <Sidebar>
      <SidebarHeader className="p-4 border-b">
        <Link to="/" className="flex items-center gap-2 px-2">
          <GraduationCap className="h-6 w-6 text-primary" />
          <span className="text-lg font-heading font-medium tracking-tight">CourseCompass</span>
        </Link>
      </SidebarHeader>
      
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="pt-4">
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton 
                  className="w-full justify-start gap-2 h-10" 
                  variant="default"
                  onClick={() => onSessionChange && onSessionChange(null)}
                >
                  <Plus className="h-4 w-4" />
                  New Chat
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Recent</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {sessions.map((chat) => (
                <SidebarMenuItem key={chat.id}>
                  <SidebarMenuButton 
                    asChild 
                    isActive={currentSessionId === chat.id}
                    onClick={() => onSessionChange && onSessionChange(chat.id)}
                  >
                    <button className="flex items-center gap-2 w-full text-left">
                      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">{chat.title}</span>
                    </button>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-auto">
          <SidebarGroupContent>
            {user && (
              <div className="px-2 py-3 mb-2 flex flex-col border-b border-border">
                <span className="text-sm font-medium truncate">{user.full_name || 'User'}</span>
                <span className="text-xs text-muted-foreground truncate">{user.registration_number}</span>
              </div>
            )}
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link to="/" className="flex items-center gap-2">
                    <LayoutDashboard className="h-4 w-4" />
                    <span>Dashboard</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <a href="#" className="flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    <span>Settings</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton onClick={logout} className="text-red-500 hover:text-red-600 hover:bg-red-50">
                  <LogOut className="h-4 w-4" />
                  <span>Logout</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
