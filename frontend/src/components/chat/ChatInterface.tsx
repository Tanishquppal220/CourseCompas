import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/context/AuthContext";

interface Message {
  id: string;
  text: string;
  sender: "user" | "bot";
}

interface ChatInterfaceProps {
  className?: string;
  sessionId?: string | null;
  onSessionChange?: (id: string) => void;
}

export function ChatInterface({ className, sessionId, onSessionChange }: ChatInterfaceProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (sessionId && token) {
      // Fetch session messages
      const fetchMessages = async () => {
        try {
          setIsLoading(true);
          const response = await fetch(`/api/chat/sessions/${sessionId}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (response.ok) {
            const data = await response.json();
            setMessages(
              data.messages.map((m: any, i: number) => ({
                id: i.toString(),
                text: m.content,
                sender: m.role === "user" ? "user" : "bot",
              }))
            );
          }
        } catch (error) {
          console.error("Failed to fetch messages:", error);
        } finally {
          setIsLoading(false);
        }
      };
      fetchMessages();
    } else {
      setMessages([
        {
          id: "1",
          text: "Hello! I am your academic assistant. Ask me about course content, exams, or your progress.",
          sender: "bot",
        },
      ]);
    }
  }, [sessionId, token]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage: Message = { id: Date.now().toString(), text: input, sender: "user" };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          messages: newMessages.map(m => ({
            role: m.sender === 'user' ? 'user' : 'assistant',
            content: m.text
          })),
          session_id: sessionId
        })
      });
      
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      
      const data = await response.json();
      
      if (data.session_id && data.session_id !== sessionId && onSessionChange) {
        onSessionChange(data.session_id);
      }
      
      setMessages(prev => [
        ...prev,
        { id: Date.now().toString(), text: data.response, sender: "bot" }
      ]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev => [
        ...prev,
        { id: Date.now().toString(), text: "Sorry, there was an error processing your request.", sender: "bot" }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={cn("flex flex-col h-[600px] border border-border rounded-xl overflow-hidden bg-background", className)}>
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-3xl mx-auto space-y-8">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-4 ${
                msg.sender === "user" ? "flex-row-reverse" : ""
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.sender === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
                }`}
              >
                {msg.sender === "user" ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div
                className={`max-w-[80%] ${
                  msg.sender === "user" ? "text-right" : ""
                }`}
              >
                {msg.sender === "user" ? (
                  <div className="bg-primary text-primary-foreground px-4 py-2 rounded-lg inline-block text-sm">
                    {msg.text}
                  </div>
                ) : (
                  <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-secondary text-secondary-foreground">
                <Bot size={16} />
              </div>
              <div className="max-w-[80%]">
                <div className="prose prose-sm dark:prose-invert">
                  <p className="text-sm leading-relaxed text-muted-foreground animate-pulse">
                    Thinking...
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-border bg-background">
        <div className="max-w-3xl mx-auto relative">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about your courses..."
            className="pr-12 h-12 text-base rounded-md"
            disabled={isLoading}
          />
          <Button
            size="icon"
            className="absolute right-1 top-1 h-10 w-10 rounded-sm"
            onClick={handleSend}
            disabled={isLoading}
          >
            <Send size={18} />
          </Button>
        </div>
      </div>
    </div>
  );
}
