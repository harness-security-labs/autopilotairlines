"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORAGE_KEY = "autopilot-chat-messages";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface FlightResult {
  id: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure: string;
  price: number;
  date: string;
  seats?: number;
}

interface BookingInfo {
  id: string;
  pnr: string;
  flight_number: string;
  origin: string;
  destination: string;
  status: string;
}

type Segment =
  | { type: "text"; content: string }
  | { type: "flight_results"; data: FlightResult[] }
  | { type: "booking_info"; data: BookingInfo }
  | { type: "quick_replies"; data: { replies: string[] } };

function parseMessageContent(content: string): Segment[] {
  const regex = /<!--ACTION:(\w+?)(\[[\s\S]*?\]|\{[\s\S]*?\})-->/g;
  const segments: Segment[] = [];
  let lastIndex = 0;

  for (const match of content.matchAll(regex)) {
    if (match.index! > lastIndex) {
      const text = content.slice(lastIndex, match.index!);
      if (text.trim()) segments.push({ type: "text", content: text });
    }
    try {
      const data = JSON.parse(match[2]);
      segments.push({ type: match[1] as Segment["type"], data } as Segment);
    } catch {
      segments.push({ type: "text", content: match[0] });
    }
    lastIndex = match.index! + match[0].length;
  }

  if (lastIndex < content.length) {
    const text = content.slice(lastIndex);
    if (text.trim()) segments.push({ type: "text", content: text });
  }

  return segments.length > 0 ? segments : [{ type: "text", content }];
}

function FlightResultsCard({ flights, onAction }: { flights: FlightResult[]; onAction: (action: string, data?: FlightResult) => void }) {
  return (
    <div className="my-3 space-y-2">
      {flights.map((f) => (
        <div key={f.id} className="flex items-center justify-between p-3 rounded-lg border border-border bg-background">
          <div className="min-w-0">
            <p className="font-medium text-sm">{f.flight_number}</p>
            <p className="text-xs text-muted-foreground">{f.origin} &rarr; {f.destination}</p>
            <p className="text-xs text-muted-foreground">{f.departure}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {f.seats !== undefined && <span className="text-[10px] text-muted-foreground">{f.seats} seats</span>}
            <span className="font-bold text-blue-600">${f.price.toFixed(2)}</span>
            <Button size="sm" onClick={() => onAction("book", f)}>Book</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function BookingInfoCard({ booking, onAction }: { booking: BookingInfo; onAction: (action: string, data?: BookingInfo) => void }) {
  return (
    <div className="my-3 p-3 rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono font-bold text-sm">{booking.pnr}</p>
          <p className="text-xs text-muted-foreground">{booking.flight_number}: {booking.origin} &rarr; {booking.destination}</p>
          <Badge variant={booking.status === "confirmed" ? "default" : "destructive"} className="mt-1 text-[10px] capitalize">{booking.status}</Badge>
        </div>
        <div className="flex gap-2 shrink-0">
          {booking.status === "confirmed" && (
            <>
              <Button size="sm" variant="outline" onClick={() => onAction("checkin", booking)}>Check In</Button>
              <Button size="sm" variant="destructive" onClick={() => onAction("cancel", booking)}>Cancel</Button>
            </>
          )}
          <Button size="sm" variant="outline" onClick={() => onAction("view_booking", booking)}>Details</Button>
        </div>
      </div>
    </div>
  );
}

function QuickReplies({ replies, onAction }: { replies: string[]; onAction: (action: string, data?: string) => void }) {
  return (
    <div className="my-2 flex flex-wrap gap-2">
      {replies.map((reply) => (
        <button
          key={reply}
          onClick={() => onAction("quick_reply", reply)}
          className="px-3 py-1.5 text-xs rounded-full border border-border bg-background hover:bg-muted transition-colors"
        >
          {reply}
        </button>
      ))}
    </div>
  );
}

function MessageContent({
  content,
  role,
  onAction,
}: {
  content: string;
  role: "user" | "assistant";
  onAction: (action: string, data?: unknown) => void;
}) {
  if (role === "user") {
    return (
      <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-blue-600 text-white rounded-tr-sm whitespace-pre-wrap">
        {content}
      </div>
    );
  }

  const segments = parseMessageContent(content);

  return (
    <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-muted text-foreground rounded-tl-sm">
      {segments.map((seg, i) => {
        if (seg.type === "text") {
          return <span key={i} className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: seg.content }} />;
        }
        if (seg.type === "flight_results") {
          return <FlightResultsCard key={i} flights={seg.data as FlightResult[]} onAction={onAction as (a: string, d?: FlightResult) => void} />;
        }
        if (seg.type === "booking_info") {
          return <BookingInfoCard key={i} booking={seg.data as BookingInfo} onAction={onAction as (a: string, d?: BookingInfo) => void} />;
        }
        if (seg.type === "quick_replies") {
          return <QuickReplies key={i} replies={(seg.data as { replies: string[] }).replies} onAction={onAction as (a: string, d?: string) => void} />;
        }
        return null;
      })}
    </div>
  );
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content: "Hello! I'm your AutoPilot Airlines AI assistant. I can help you search flights, book tickets, manage bookings, check loyalty points, and more. How can I help you today?<!--ACTION:quick_replies{\"replies\":[\"Search flights\",\"View my bookings\",\"Check loyalty points\",\"Help\"]}-->",
};

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Message[];
        if (parsed.length > 0) setMessages(parsed);
      }
    } catch {}
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch {}
    }
  }, [messages, hydrated]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollH = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = Math.min(scrollH, 150) + "px";
      textareaRef.current.style.overflowY = scrollH > 150 ? "auto" : "hidden";
    }
  }, [input]);

  const sendMessage = useCallback(async (overrideInput?: string) => {
    const text = overrideInput ?? input;
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text.trim(),
    };
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const allMessages = [...messages, userMessage]
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content.replace(/<!--ACTION:[\s\S]*?-->/g, "").trim() }))
        .filter((m) => m.content);

      const res = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ messages: allMessages }),
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ") && line !== "data: [DONE]") {
              try {
                const data = JSON.parse(line.slice(6));
                const content = data.choices?.[0]?.delta?.content || "";
                fullContent += content;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? { ...m, content: fullContent } : m
                  )
                );
              } catch {}
            }
          }
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? { ...m, content: "Sorry, I encountered an error. Please try again." }
            : m
        )
      );
    }
    setIsLoading(false);
    textareaRef.current?.focus();
  }, [input, isLoading, messages]);

  const handleAction = useCallback((action: string, data?: unknown) => {
    switch (action) {
      case "book": {
        const f = data as FlightResult;
        router.push(`/book/${f.id}?date=${f.date}`);
        break;
      }
      case "cancel": {
        const b = data as BookingInfo;
        sendMessage(`Cancel my booking ${b.pnr}`);
        break;
      }
      case "checkin": {
        const b = data as BookingInfo;
        router.push(`/checkin?pnr=${b.pnr}`);
        break;
      }
      case "view_booking": {
        const b = data as BookingInfo;
        router.push(`/bookings/${b.id}`);
        break;
      }
      case "quick_reply": {
        sendMessage(data as string);
        break;
      }
    }
  }, [router, sendMessage]);

  const clearChat = () => {
    setMessages([WELCOME_MESSAGE]);
    localStorage.removeItem(STORAGE_KEY);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!hydrated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6 h-[calc(100vh-3.5rem)] flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border">
        <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
          </svg>
        </div>
        <div className="flex-1">
          <h1 className="text-sm font-semibold">AI Travel Assistant</h1>
          <p className="text-xs text-muted-foreground">AutoPilot Airlines</p>
        </div>
        <button
          onClick={clearChat}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded-md hover:bg-muted"
          title="Clear chat history"
        >
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="space-y-4 pb-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div className={`flex gap-2.5 max-w-[85%] ${message.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                  message.role === "user"
                    ? "bg-slate-800 text-white dark:bg-slate-600"
                    : "bg-blue-600 text-white"
                }`}>
                  {message.role === "user" ? (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                    </svg>
                  )}
                </div>
                <MessageContent
                  content={message.content}
                  role={message.role}
                  onAction={handleAction}
                />
              </div>
            </div>
          ))}
          {isLoading && messages[messages.length - 1]?.content === "" && (
            <div className="flex justify-start">
              <div className="flex gap-2.5 max-w-[80%]">
                <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-blue-600 text-white">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                  </svg>
                </div>
                <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border pt-4">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about flights, bookings, loyalty points..."
            disabled={isLoading}
            autoFocus
            rows={1}
            className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground focus-visible:border-blue-400 focus-visible:ring-2 focus-visible:ring-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
            style={{ minHeight: "40px", maxHeight: "150px" }}
          />
          <Button
            onClick={() => sendMessage()}
            disabled={isLoading || !input.trim()}
            className="h-10 w-10 p-0 flex-shrink-0"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground text-center mt-2">
          Enter to send &middot; Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
