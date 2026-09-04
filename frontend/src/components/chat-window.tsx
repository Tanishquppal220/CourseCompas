"use client";

import { useEffect, useRef, useState } from "react";

import { ChatHeader } from "@/components/chat-header";
import { ChatInput } from "@/components/chat-input";
import { MessageScroller } from "@/components/message-scroller";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  response: string;
  sources?: {
    source: string;
    course_code?: string | null;
    score?: number;
  }[];
}

const sendMessageToBackend = async (message: string): Promise<ChatResponse> => {
  const response = await fetch("http://localhost:8000/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages: [
        {
          role: "user",
          content: message,
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  return response.json();
};

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

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
      const response = await sendMessageToBackend(input);

      let content = response.response;
      if (response.sources?.length) {
        const names = response.sources.map((s) => s.source);
        content += `\n\n**Sources:** ${names.join(" · ")}`;
      }

      const aiMessage: ChatMessage = {
        role: "assistant",
        content,
      };

      setMessages((prev) => [...prev, aiMessage]);
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
      <ChatHeader />

      <MessageScroller
        messages={messages}
        isLoading={isLoading}
        messagesEndRef={messagesEndRef}
      />

      <ChatInput onSend={handleSendMessage} disabled={isLoading} />
    </div>
  );
}
