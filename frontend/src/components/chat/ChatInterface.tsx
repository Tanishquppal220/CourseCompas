import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  text: string;
  sender: "user" | "bot";
}

export function ChatInterface({ className }: { className?: string }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      text: "Hello! I am your academic assistant. Ask me about course content, exams, or your progress.",
      sender: "bot",
    },
  ]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), text: input, sender: "user" },
    ]);
    setInput("");

    // Simulate response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: "I am a prototype responding to your query about: " + input,
          sender: "bot",
        },
      ]);
    }, 1000);
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
                  <div className="prose prose-sm dark:prose-invert">
                    <p className="text-sm leading-relaxed text-foreground">
                      {msg.text}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
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
          />
          <Button
            size="icon"
            className="absolute right-1 top-1 h-10 w-10 rounded-sm"
            onClick={handleSend}
          >
            <Send size={18} />
          </Button>
        </div>
      </div>
    </div>
  );
}
