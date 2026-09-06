"use client";

import { useEffect, useState } from "react";
import {
  Plus,
  MessageSquare,
  LogIn,
  UserPlus,
  User as UserIcon,
  Compass,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../lib/authContext";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
} from "@/components/ui/sidebar";

interface ChatSession {
  id: string;
  title: string;
}

export function AppSidebar() {
  const { user, token } = useAuth();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const location = useLocation();

  useEffect(() => {
    if (user && token) {
      fetch("/api/chat/sessions", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data)) setSessions(data);
        })
        .catch(console.error);
    } else {
      setSessions([]);
    }
  }, [user, token, location.pathname]);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          {/* Branding */}
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link to="/" />}>
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Compass className="h-4 w-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">CourseCompass</span>
                <span className="truncate text-xs text-muted-foreground">
                  AI Academic Advisor
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>

          {/* New Chat */}
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="New Chat" render={<Link to="/" />}>
              <Plus className="h-4 w-4" />
              <span>New Chat</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {sessions.length > 0 && (
          <SidebarGroup>
            <SidebarGroupLabel>Recent conversations</SidebarGroupLabel>
            <SidebarMenu>
              {sessions.map((session) => (
                <SidebarMenuItem key={session.id}>
                  <SidebarMenuButton
                    tooltip={session.title}
                    render={<Link to={`/chat/${session.id}`} />}
                  >
                    <MessageSquare className="h-4 w-4" />
                    <span>{session.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          {user ? (
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                tooltip="My Profile"
                render={<Link to="/profile" />}
              >
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarImage src="/avatar.png" alt="User profile" />
                  <AvatarFallback className="rounded-lg">
                    <UserIcon className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">
                    {user.registration_number}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {user.program || "Student"}
                  </span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ) : (
            <>
              <SidebarMenuItem>
                <SidebarMenuButton tooltip="Login" render={<Link to="/login" />}>
                  <LogIn className="h-4 w-4" />
                  <span>Login</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Register"
                  render={<Link to="/register" />}
                >
                  <UserPlus className="h-4 w-4" />
                  <span>Register</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </>
          )}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
