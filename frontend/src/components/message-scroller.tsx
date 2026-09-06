import {
  Compass,
  BookOpen,
  Award,
  FileText,
  Clock,
  Loader2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface MessageScrollerProps {
  messages: ChatMessage[];
  isLoading: boolean;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  onSuggestionClick?: (text: string) => void;
}

const suggestions = [
  { icon: BookOpen, text: "What courses are in Semester 5?" },
  { icon: Award, text: "What is LPU EduRevolution & what benefits can I claim?" },
  { icon: FileText, text: "Show me the syllabus for CSE202" },
  { icon: Clock, text: "What are the attendance benefits?" },
];

export function MessageScroller({
  messages,
  isLoading,
  messagesEndRef,
  onSuggestionClick,
}: MessageScrollerProps) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-8 px-4 pt-16">
            {/* Hero */}
            <div className="flex flex-col items-center gap-3 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                <Compass className="h-8 w-8 text-primary" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">
                CourseCompass
              </h1>
              <p className="max-w-sm text-sm text-muted-foreground">
                Your AI Academic Advisor — ask about courses, policies, grades &
                more
              </p>
            </div>

            {/* Suggestion cards */}
            <div className="grid w-full max-w-lg grid-cols-2 gap-3">
              {suggestions.map((s) => (
                <button
                  key={s.text}
                  onClick={() => onSuggestionClick?.(s.text)}
                  className="flex items-start gap-3 rounded-xl border bg-card p-4 text-left text-sm transition-colors hover:bg-accent"
                >
                  <s.icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>{s.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                message.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              <div
                className={
                  message.role === "assistant"
                    ? "prose prose-sm dark:prose-invert max-w-none"
                    : ""
                }
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw, rehypeHighlight]}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-3">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
