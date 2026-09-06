"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/authContext";

import { ChatHeader } from "@/components/chat-header";
import { ChatInput } from "@/components/chat-input";
import { MessageScroller } from "@/components/message-scroller";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  response: string;
  sources?: (
    | string
    | {
        source: string;
        course_code?: string | null;
        score?: number;
      }
  )[];
  session_id?: string;
}

export function ChatWindow() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { token } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionTitle, setSessionTitle] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load history when session id changes
  useEffect(() => {
    if (id && token) {
      setIsLoading(true);
      fetch(`/api/chat/sessions/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.messages) setMessages(data.messages);
          if (data.title) setSessionTitle(data.title);
        })
        .catch(console.error)
        .finally(() => setIsLoading(false));
    } else {
      setMessages([]);
      setSessionTitle("");
    }
  }, [id, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages]);

  const handleSendMessage = async (input: string) => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          messages: [...messages, userMessage],
          session_id: id || undefined,
        }),
      });

      if (!response.ok) throw new Error("Failed to send message");

      const data: ChatResponse = await response.json();

      let content = data.response;
      if (data.sources?.length) {
        const names = data.sources.map((s) =>
          typeof s === "string" ? s : s.source
        );
        content += `\n\n> 📚 **Referenced Sources:**\n${names.map((n) => `> - ${n}`).join("\n")}`;
      }

      const aiMessage: ChatMessage = {
        role: "assistant",
        content,
      };

      setMessages((prev) => [...prev, aiMessage]);

      if (!id && data.session_id) {
        navigate(`/chat/${data.session_id}`);
      }
    } catch (error) {
      console.error("Error sending message:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ChatHeader title={sessionTitle} />

      <MessageScroller
        messages={messages}
        isLoading={isLoading}
        messagesEndRef={messagesEndRef}
        onSuggestionClick={handleSendMessage}
      />

      <ChatInput onSend={handleSendMessage} disabled={isLoading} />
    </div>
  );
}
