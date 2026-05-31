"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Markdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/lib/store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORAGE_KEY_PREFIX = "autopilot-chat-messages";

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

interface BookingListItem {
  id: string;
  pnr: string;
  flight_number: string;
  origin: string;
  destination: string;
  travel_date: string | null;
  status: string;
  cabin_class: string;
}

interface LoyaltyInfo {
  points: number;
  tier: string;
  points_value: number;
  tier_expiry: string | null;
}

interface CouponResult {
  valid: boolean;
  code: string;
  discount_percent: number;
  description: string;
}

interface ReportDownload {
  report_id: string;
  title: string;
  url: string;
}

type Segment =
  | { type: "text"; content: string }
  | { type: "flight_results"; data: FlightResult[] }
  | { type: "booking_info"; data: BookingInfo }
  | { type: "booking_list"; data: BookingListItem[] }
  | { type: "loyalty_info"; data: LoyaltyInfo }
  | { type: "coupon_result"; data: CouponResult }
  | { type: "report_download"; data: ReportDownload }
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
            <Button size="sm" onClick={() => onAction("select_flight", f)}>Select</Button>
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

function BookingListCard({ bookings, onAction }: { bookings: BookingListItem[]; onAction: (action: string, data?: BookingListItem) => void }) {
  const statusColor = (s: string) => {
    if (s === "confirmed") return "default" as const;
    if (s === "cancelled") return "destructive" as const;
    return "secondary" as const;
  };
  return (
    <div className="my-3 space-y-2">
      {bookings.map((b) => (
        <div key={b.id} className="flex items-center justify-between p-3 rounded-lg border border-border bg-background">
          <div className="min-w-0">
            <p className="font-mono font-bold text-sm">{b.pnr}</p>
            <p className="text-xs text-muted-foreground">{b.flight_number}: {b.origin} &rarr; {b.destination}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={statusColor(b.status)} className="text-[10px] capitalize">{b.status}</Badge>
              <span className="text-[10px] text-muted-foreground capitalize">{b.cabin_class}</span>
              {b.travel_date && <span className="text-[10px] text-muted-foreground">{b.travel_date}</span>}
            </div>
          </div>
          <Button size="sm" variant="outline" onClick={() => onAction("view_booking", b)}>Details</Button>
        </div>
      ))}
    </div>
  );
}

function LoyaltyInfoCard({ info, onAction }: { info: LoyaltyInfo; onAction: (action: string) => void }) {
  const tierColor = (t: string) => {
    if (t === "platinum") return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
    if (t === "gold") return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    if (t === "silver") return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200";
    return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
  };
  return (
    <div className="my-3 p-4 rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Loyalty Status</h4>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${tierColor(info.tier)}`}>{info.tier}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-bold">{info.points.toLocaleString()}</span>
        <span className="text-xs text-muted-foreground">points</span>
      </div>
      <p className="text-xs text-muted-foreground mt-1">Worth ${info.points_value.toFixed(2)}</p>
      {info.tier_expiry && <p className="text-[10px] text-muted-foreground mt-2">Tier expires: {info.tier_expiry}</p>}
      <Button size="sm" variant="outline" className="mt-3" onClick={() => onAction("view_loyalty")}>View Full Details</Button>
    </div>
  );
}

function CouponResultCard({ result }: { result: CouponResult }) {
  return (
    <div className={`my-3 p-3 rounded-lg border ${result.valid ? "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950" : "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950"}`}>
      <div className="flex items-center gap-2">
        {result.valid ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-green-600" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-red-600" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
          </svg>
        )}
        <span className="font-mono font-bold text-sm">{result.code}</span>
        {result.valid && <Badge className="text-[10px]">{result.discount_percent}% off</Badge>}
      </div>
      <p className="text-xs mt-1.5 text-muted-foreground">{result.description}</p>
    </div>
  );
}

function ReportDownloadCard({ report }: { report: ReportDownload }) {
  const handleDownload = () => {
    window.open(`${API_URL}${report.url}`, "_blank");
  };
  return (
    <div className="my-3 p-3 rounded-lg border border-border bg-background flex items-center justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <div className="shrink-0 w-9 h-9 rounded-lg bg-red-50 dark:bg-red-950 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-red-600" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{report.title}</p>
          <p className="text-[10px] text-muted-foreground font-mono">{report.report_id}.pdf</p>
        </div>
      </div>
      <Button size="sm" variant="outline" onClick={handleDownload}>
        Download PDF
      </Button>
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
          return <div key={i} className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 prose-pre:my-2 prose-code:text-xs"><Markdown>{seg.content}</Markdown></div>;
        }
        if (seg.type === "flight_results") {
          return <FlightResultsCard key={i} flights={seg.data as FlightResult[]} onAction={onAction as (a: string, d?: FlightResult) => void} />;
        }
        if (seg.type === "booking_info") {
          return <BookingInfoCard key={i} booking={seg.data as BookingInfo} onAction={onAction as (a: string, d?: BookingInfo) => void} />;
        }
        if (seg.type === "booking_list") {
          return <BookingListCard key={i} bookings={seg.data as BookingListItem[]} onAction={onAction as (a: string, d?: BookingListItem) => void} />;
        }
        if (seg.type === "loyalty_info") {
          return <LoyaltyInfoCard key={i} info={seg.data as LoyaltyInfo} onAction={onAction as (a: string) => void} />;
        }
        if (seg.type === "coupon_result") {
          return <CouponResultCard key={i} result={seg.data as CouponResult} />;
        }
        if (seg.type === "report_download") {
          return <ReportDownloadCard key={i} report={seg.data as ReportDownload} />;
        }
        if (seg.type === "quick_replies") {
          return <QuickReplies key={i} replies={(seg.data as { replies: string[] }).replies} onAction={onAction as (a: string, d?: string) => void} />;
        }
        return null;
      })}
    </div>
  );
}

const AGENT_LABELS: Record<string, { label: string; color: string }> = {
  booking: { label: "Booking Agent", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
  payment: { label: "Payment Agent", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
  customer_service: { label: "Customer Service", color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200" },
  admin: { label: "Admin Agent", color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
};

function AgentBadge({ agent }: { agent: string | null }) {
  if (!agent || !AGENT_LABELS[agent]) return null;
  const { label, color } = AGENT_LABELS[agent];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${color}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70 animate-pulse" />
      {label}
    </span>
  );
}

const WELCOME_MESSAGE_LOGGED_IN: Message = {
  id: "welcome",
  role: "assistant",
  content: "Hello! I'm your AutoPilot Airlines AI assistant. I can help you search flights, book tickets, manage bookings, check loyalty points, and more. How can I help you today?<!--ACTION:quick_replies{\"replies\":[\"Search flights\",\"View my bookings\",\"Check loyalty points\",\"Help\"]}-->",
};

const WELCOME_MESSAGE_GUEST: Message = {
  id: "welcome",
  role: "assistant",
  content: "Welcome to AutoPilot Airlines! Browse available flights, or log in to book tickets, manage bookings, and access your loyalty points.<!--ACTION:quick_replies{\"replies\":[\"Search flights\",\"Log in\",\"Create account\"]}-->",
};

export default function ChatPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const loadToken = useAuthStore((s) => s.loadToken);
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE_GUEST]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [hydrated, setHydrated] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const prevUserRef = useRef<string | null>(null);

  const getStorageKey = useCallback((email?: string | null) => {
    return `${STORAGE_KEY_PREFIX}:${email || "guest"}`;
  }, []);

  useEffect(() => {
    loadToken();
  }, [loadToken]);

  useEffect(() => {
    if (user?.email) {
      const key = getStorageKey(user.email);
      try {
        const stored = localStorage.getItem(key);
        if (stored) {
          const parsed = JSON.parse(stored) as Message[];
          if (parsed.length > 0) {
            setMessages(parsed);
            setHydrated(true);
            return;
          }
        }
      } catch {}
      setMessages([WELCOME_MESSAGE_LOGGED_IN]);
    } else {
      setMessages([WELCOME_MESSAGE_GUEST]);
    }
    setHydrated(true);
  }, [user, getStorageKey]);

  useEffect(() => {
    const currentUser = user?.email || null;
    if (prevUserRef.current !== currentUser && prevUserRef.current !== null) {
      setActiveAgent(null);
      setSessionId(crypto.randomUUID());
    }
    prevUserRef.current = currentUser;
  }, [user]);

  useEffect(() => {
    if (hydrated && user?.email) {
      const key = getStorageKey(user.email);
      try {
        localStorage.setItem(key, JSON.stringify(messages));
      } catch {}
    }
  }, [messages, hydrated, user, getStorageKey]);

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
        body: JSON.stringify({ messages: allMessages, session_id: sessionId }),
      });

      if (!res.ok) {
        let errorDetail = `Server error (${res.status})`;
        try {
          const body = await res.text();
          const parsed = JSON.parse(body);
          if (parsed.detail) errorDetail = parsed.detail;
        } catch {}
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? { ...m, content: `Something went wrong: ${errorDetail}. Please try again.` }
              : m
          )
        );
        setIsLoading(false);
        return;
      }

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
                if (data.error) {
                  fullContent = `Something went wrong: ${data.error}. Please try again.`;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMessage.id ? { ...m, content: fullContent } : m
                    )
                  );
                  break;
                }
                const content = data.choices?.[0]?.delta?.content || "";
                fullContent += content;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? { ...m, content: fullContent } : m
                  )
                );
                if (data.active_agent !== undefined) {
                  setActiveAgent(data.active_agent);
                }
              } catch {}
            }
          }
        }
      }

      if (!fullContent.trim()) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? { ...m, content: "Something went wrong: no response received. Please try again." }
              : m
          )
        );
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? { ...m, content: "Something went wrong: connection failed. Please try again." }
            : m
        )
      );
    }
    setIsLoading(false);
    textareaRef.current?.focus();
  }, [input, isLoading, messages, sessionId]);

  const handleAction = useCallback((action: string, data?: unknown) => {
    switch (action) {
      case "select_flight": {
        const f = data as FlightResult;
        sendMessage(`I'll take flight ${f.flight_number} on ${f.date}`);
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
      case "view_loyalty": {
        router.push("/loyalty");
        break;
      }
      case "quick_reply": {
        const text = data as string;
        if (text.toLowerCase() === "log in" || text.toLowerCase() === "create account") {
          router.push("/login");
          return;
        }
        sendMessage(text);
        break;
      }
    }
  }, [router, sendMessage]);

  const clearChat = () => {
    setMessages([user ? WELCOME_MESSAGE_LOGGED_IN : WELCOME_MESSAGE_GUEST]);
    setActiveAgent(null);
    localStorage.removeItem(getStorageKey(user?.email));
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
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold">AI Travel Assistant</h1>
            <AgentBadge agent={activeAgent} />
          </div>
          {!user && (
            <p className="text-xs text-muted-foreground">
              Sign in for personalized help
            </p>
          )}
        </div>
        {user && (
          <span className="text-xs text-muted-foreground">
            {user.name || user.email}
          </span>
        )}
        {!user && (
          <Button size="sm" variant="outline" onClick={() => router.push("/login")}>
            Sign In
          </Button>
        )}
        <div className="flex items-center gap-2">
          {activeAgent && (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => sendMessage("end conversation")}
            >
              End session
            </Button>
          )}
          <Button
            size="sm"
            variant="secondary"
            onClick={clearChat}
          >
            Clear chat
          </Button>
        </div>
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
                    user ? (
                      <span className="text-[10px] font-semibold">
                        {(user.name || user.email).charAt(0).toUpperCase()}
                      </span>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    )
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
