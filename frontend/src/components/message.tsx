interface MessageProps {
    role: "user" | "assistant";
    children: React.ReactNode;
  }
  
  export function Message({
    role,
    children,
  }: MessageProps) {
    const isUser = role === "user";
  
    return (
      <div
        className={`flex ${
          isUser ? "justify-end" : "justify-start"
        }`}
      >
        <div
          className={`max-w-[80%] rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          }`}
        >
          {children}
        </div>
      </div>
    );
  }