"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const AIRPORTS: { code: string; city: string; country: string }[] = [
  { code: "SFO", city: "San Francisco", country: "US" },
  { code: "JFK", city: "New York", country: "US" },
  { code: "LAX", city: "Los Angeles", country: "US" },
  { code: "ORD", city: "Chicago", country: "US" },
  { code: "MIA", city: "Miami", country: "US" },
  { code: "SEA", city: "Seattle", country: "US" },
  { code: "BOS", city: "Boston", country: "US" },
  { code: "ATL", city: "Atlanta", country: "US" },
  { code: "DFW", city: "Dallas", country: "US" },
  { code: "DEL", city: "New Delhi", country: "IN" },
  { code: "BOM", city: "Mumbai", country: "IN" },
  { code: "BLR", city: "Bengaluru", country: "IN" },
  { code: "HYD", city: "Hyderabad", country: "IN" },
  { code: "MAA", city: "Chennai", country: "IN" },
  { code: "CCU", city: "Kolkata", country: "IN" },
  { code: "LHR", city: "London", country: "UK" },
  { code: "CDG", city: "Paris", country: "FR" },
  { code: "FRA", city: "Frankfurt", country: "DE" },
  { code: "DXB", city: "Dubai", country: "AE" },
  { code: "SIN", city: "Singapore", country: "SG" },
  { code: "HKG", city: "Hong Kong", country: "HK" },
  { code: "NRT", city: "Tokyo", country: "JP" },
  { code: "ICN", city: "Seoul", country: "KR" },
  { code: "SYD", city: "Sydney", country: "AU" },
  { code: "GRU", city: "São Paulo", country: "BR" },
  { code: "MEX", city: "Mexico City", country: "MX" },
  { code: "YVR", city: "Vancouver", country: "CA" },
  { code: "MLE", city: "Malé", country: "MV" },
  { code: "CUN", city: "Cancún", country: "MX" },
];

function AirportDropdown({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { setQuery(value); }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = AIRPORTS.filter((a) => {
    const q = query.toLowerCase();
    return !q || a.code.toLowerCase().includes(q) || a.city.toLowerCase().includes(q) || a.country.toLowerCase().includes(q);
  });

  const selectedAirport = AIRPORTS.find((a) => a.code === value.toUpperCase());

  return (
    <div ref={ref} className="relative">
      <Input
        placeholder={placeholder}
        value={query}
        onChange={(e) => { setQuery(e.target.value); onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        className="uppercase"
      />
      {selectedAirport && !open && (
        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{selectedAirport.city}, {selectedAirport.country}</p>
      )}
      {open && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-white dark:bg-slate-900 border border-border rounded-lg shadow-xl animate-fade-in">
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">No airports found</div>
          ) : (
            filtered.map((a) => (
              <button
                key={a.code}
                type="button"
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors"
                onClick={() => { onChange(a.code); setQuery(a.code); setOpen(false); }}
              >
                <span className="font-mono font-semibold text-sm w-10">{a.code}</span>
                <span className="text-xs text-muted-foreground truncate">{a.city}, {a.country}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

interface CabinAvailability {
  seats: number;
  available: number;
  price: number;
}

interface Flight {
  id: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  aircraft: string;
  status: string;
  base_price: number;
  price: number;
  available_seats: number;
  total_seats: number;
  days_of_week: string | null;
  valid_from: string | null;
  valid_until: string | null;
  stops: number;
  via: string | null;
  segments: { flight: string; from: string; to: string; dep: string; arr: string; price: number }[] | null;
  cabin_classes: Record<string, CabinAvailability> | null;
}

function formatSchedule(days: string | null, validFrom: string | null, validUntil: string | null): string {
  if (!days) return "One-off";
  if (validFrom || validUntil) return "Seasonal";
  if (days === "0123456") return "Daily";
  if (days === "01234") return "Weekdays";
  if (days === "56") return "Weekends";
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return days.split("").map(d => names[parseInt(d)]).join("/");
}

const POPULAR_ROUTES = [
  { origin: "DEL", destination: "BOM", label: "Delhi → Mumbai", emoji: "🇮🇳" },
  { origin: "JFK", destination: "LAX", label: "New York → Los Angeles", emoji: "🇺🇸" },
  { origin: "LHR", destination: "JFK", label: "London → New York", emoji: "🌍" },
  { origin: "SFO", destination: "NRT", label: "San Francisco → Tokyo", emoji: "🌏" },
  { origin: "DXB", destination: "LHR", label: "Dubai → London", emoji: "✈️" },
  { origin: "BLR", destination: "SIN", label: "Bengaluru → Singapore", emoji: "🌏" },
  { origin: "DEL", destination: "DXB", label: "Delhi → Dubai", emoji: "🌍" },
  { origin: "ORD", destination: "MIA", label: "Chicago → Miami", emoji: "🇺🇸" },
];

interface PastRoute {
  origin: string;
  destination: string;
  count: number;
}

export default function Home() {
  const now = new Date();
  const defaultDate = now.getHours() >= 20
    ? new Date(now.getTime() + 86400000).toISOString().split("T")[0]
    : now.toISOString().split("T")[0];
  const [tripType, setTripType] = useState<"oneway" | "roundtrip">("roundtrip");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState(defaultDate);
  const [returnDate, setReturnDate] = useState(defaultDate);
  const [flights, setFlights] = useState<Flight[]>([]);
  const [returnFlights, setReturnFlights] = useState<Flight[]>([]);
  const [loading, setLoading] = useState(false);
  const [stopsFilter, setStopsFilter] = useState<number | null>(null);
  const [flexPrices, setFlexPrices] = useState<{ date: string; min_price: number }[]>([]);
  const [returnFlexPrices, setReturnFlexPrices] = useState<{ date: string; min_price: number }[]>([]);
  const [flexBefore, setFlexBefore] = useState(0);
  const [flexAfter, setFlexAfter] = useState(0);
  const [expandedFlight, setExpandedFlight] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"outbound" | "return">("outbound");
  const [selectedOutbound, setSelectedOutbound] = useState<Flight | null>(null);
  const [pastRoutes, setPastRoutes] = useState<PastRoute[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;
    fetch(`${API_URL}/api/v1/bookings`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then(async (bookings: { flight_id: string }[]) => {
        if (!bookings.length) return;
        const routeCount: Record<string, { origin: string; destination: string; count: number }> = {};
        const flightCache: Record<string, { origin: string; destination: string }> = {};
        for (const b of bookings.slice(0, 20)) {
          if (!flightCache[b.flight_id]) {
            try {
              const r = await fetch(`${API_URL}/api/v1/flights/${b.flight_id}`);
              if (r.ok) {
                const f = await r.json();
                flightCache[b.flight_id] = { origin: f.origin, destination: f.destination };
              }
            } catch {}
          }
          const cached = flightCache[b.flight_id];
          if (cached) {
            const key = `${cached.origin}-${cached.destination}`;
            if (!routeCount[key]) routeCount[key] = { origin: cached.origin, destination: cached.destination, count: 0 };
            routeCount[key].count++;
          }
        }
        const sorted = Object.values(routeCount).sort((a, b) => b.count - a.count).slice(0, 4);
        setPastRoutes(sorted);
      })
      .catch(() => {});
  }, []);

  const searchFlights = async (searchDate?: string, isReturn?: boolean) => {
    setLoading(true);
    const d = searchDate || date;
    const params = new URLSearchParams();
    if (origin) params.set("origin", isReturn ? destination : origin);
    if (destination) params.set("destination", isReturn ? origin : destination);
    if (isReturn) {
      const rd = searchDate || returnDate;
      if (rd) params.set("date", rd);
    } else {
      if (d) params.set("date", d);
    }
    try {
      const res = await fetch(`${API_URL}/api/v1/flights/search?${params}`);
      const data = await res.json();
      if (isReturn) {
        setReturnFlights(data);
        if (searchDate) setReturnDate(searchDate);
      } else {
        setFlights(data);
        if (searchDate) setDate(searchDate);
        // Also fetch return flights for round trip
        if (tripType === "roundtrip" && returnDate) {
          const rParams = new URLSearchParams();
          rParams.set("origin", destination);
          rParams.set("destination", origin);
          rParams.set("date", returnDate);
          const rRes = await fetch(`${API_URL}/api/v1/flights/search?${rParams}`);
          const rData = await rRes.json();
          setReturnFlights(rData);
        }
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const searchAll = async () => {
    setLoading(true);
    setSelectedOutbound(null);
    setActiveTab("outbound");
    await new Promise((r) => setTimeout(r, 800 + Math.random() * 700));
    const params = new URLSearchParams();
    if (origin) params.set("origin", origin);
    if (destination) params.set("destination", destination);
    if (date) params.set("date", date);
    try {
      const res = await fetch(`${API_URL}/api/v1/flights/search?${params}`);
      const data = await res.json();
      setFlights(data);

      if (tripType === "roundtrip" && returnDate && origin && destination) {
        const rParams = new URLSearchParams();
        rParams.set("origin", destination);
        rParams.set("destination", origin);
        rParams.set("date", returnDate);
        const rRes = await fetch(`${API_URL}/api/v1/flights/search?${rParams}`);
        const rData = await rRes.json();
        setReturnFlights(rData);
      } else {
        setReturnFlights([]);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const loadFlexPrices = async () => {
    if (!date || !origin || !destination || (flexBefore === 0 && flexAfter === 0)) {
      setFlexPrices([]);
      setReturnFlexPrices([]);
      return;
    }
    const prices: { date: string; min_price: number }[] = [];
    const baseDate = new Date(date + "T00:00:00");
    const fetches = [];
    for (let i = -flexBefore; i <= flexAfter; i++) {
      const d = new Date(baseDate);
      d.setDate(d.getDate() + i);
      const ds = d.toISOString().split("T")[0];
      fetches.push(
        fetch(`${API_URL}/api/v1/flights/search?origin=${origin}&destination=${destination}&date=${ds}`)
          .then(r => r.ok ? r.json() : [])
          .then(data => {
            const directFlights = data.filter((f: Flight) => f.stops === 0);
            const minP = directFlights.length > 0 ? Math.min(...directFlights.map((f: Flight) => f.price)) : null;
            prices.push({ date: ds, min_price: minP ?? 0 });
          })
          .catch(() => prices.push({ date: ds, min_price: 0 }))
      );
    }
    await Promise.all(fetches);
    prices.sort((a, b) => a.date.localeCompare(b.date));
    setFlexPrices(prices);

    if (tripType === "roundtrip" && returnDate) {
      const rPrices: { date: string; min_price: number }[] = [];
      const rBase = new Date(returnDate + "T00:00:00");
      const rFetches = [];
      for (let i = -flexBefore; i <= flexAfter; i++) {
        const d = new Date(rBase);
        d.setDate(d.getDate() + i);
        const ds = d.toISOString().split("T")[0];
        rFetches.push(
          fetch(`${API_URL}/api/v1/flights/search?origin=${destination}&destination=${origin}&date=${ds}`)
            .then(r => r.ok ? r.json() : [])
            .then(data => {
              const directFlights = data.filter((f: Flight) => f.stops === 0);
              const minP = directFlights.length > 0 ? Math.min(...directFlights.map((f: Flight) => f.price)) : null;
              rPrices.push({ date: ds, min_price: minP ?? 0 });
            })
            .catch(() => rPrices.push({ date: ds, min_price: 0 }))
        );
      }
      await Promise.all(rFetches);
      rPrices.sort((a, b) => a.date.localeCompare(b.date));
      setReturnFlexPrices(rPrices);
    }
  };

  useEffect(() => {
    if (flights.length > 0 && date && origin && destination) {
      loadFlexPrices();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flights.length, date, returnDate, flexBefore, flexAfter]);

  const currentFlights = activeTab === "return" ? returnFlights : flights;
  const filteredFlights = stopsFilter !== null ? currentFlights.filter(f => f.stops === stopsFilter) : currentFlights;
  const currentFlexPrices = activeTab === "return" ? returnFlexPrices : flexPrices;

  return (
    <div className="min-h-[calc(100vh-3.5rem)]">
      {/* Hero */}
      <div className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 dark:from-blue-900 dark:via-blue-950 dark:to-indigo-950">
        {/* Animated background elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-10 left-[10%] w-64 h-64 bg-blue-400/10 rounded-full blur-3xl animate-float" />
          <div className="absolute bottom-10 right-[15%] w-48 h-48 bg-indigo-400/10 rounded-full blur-3xl animate-float" style={{ animationDelay: "1.5s" }} />
          <svg xmlns="http://www.w3.org/2000/svg" className="absolute top-8 right-[20%] w-8 h-8 text-white/10 animate-plane" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
          </svg>
        </div>

        <div className="relative max-w-5xl mx-auto px-4 py-16 sm:py-20 text-center">
          <div className="animate-fade-in">
            <h1 className="text-3xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
              Fly Smarter with AI
            </h1>
            <p className="text-blue-100/90 max-w-xl mx-auto mb-10 text-base sm:text-lg">
              Search flights, book tickets, and manage your travel — powered by intelligent automation.
            </p>
          </div>

          {/* Search */}
          <Card className="max-w-3xl mx-auto p-5 sm:p-6 text-left shadow-2xl shadow-blue-900/20 animate-slide-up">
            <div className="flex gap-2 mb-4">
              <button
                type="button"
                onClick={() => setTripType("roundtrip")}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  tripType === "roundtrip" ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                Round Trip
              </button>
              <button
                type="button"
                onClick={() => { setTripType("oneway"); setReturnFlights([]); setSelectedOutbound(null); }}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  tripType === "oneway" ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                One Way
              </button>
            </div>
            <div className={`grid grid-cols-1 gap-3 items-start ${tripType === "roundtrip" ? "sm:grid-cols-[1fr_1fr_auto_auto_auto]" : "sm:grid-cols-[1fr_1fr_auto_auto]"}`}>
              <div className="min-w-0">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">From</label>
                <AirportDropdown placeholder="City or code" value={origin} onChange={setOrigin} />
              </div>
              <div className="min-w-0">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">To</label>
                <AirportDropdown placeholder="City or code" value={destination} onChange={setDestination} />
              </div>
              <div className="min-w-0">
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Depart</label>
                <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} min={defaultDate} className="w-[140px]" />
              </div>
              {tripType === "roundtrip" && (
                <div className="min-w-0">
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Return</label>
                  <Input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} min={date || defaultDate} className="w-[140px]" />
                </div>
              )}
              <div className="pt-[18px]">
                <Button onClick={() => searchAll()} disabled={loading} className="w-full whitespace-nowrap">
                  Search Flights
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border/50">
              <label className="text-xs font-medium text-muted-foreground whitespace-nowrap">Flexible</label>
              <select
                value={flexBefore}
                onChange={(e) => setFlexBefore(Number(e.target.value))}
                className="h-8 px-2 rounded-md border border-border bg-background text-xs"
              >
                <option value={0}>- 0 days</option>
                <option value={1}>- 1 day</option>
                <option value={2}>- 2 days</option>
                <option value={3}>- 3 days</option>
                <option value={5}>- 5 days</option>
                <option value={7}>- 7 days</option>
              </select>
              <select
                value={flexAfter}
                onChange={(e) => setFlexAfter(Number(e.target.value))}
                className="h-8 px-2 rounded-md border border-border bg-background text-xs"
              >
                <option value={0}>+ 0 days</option>
                <option value={1}>+ 1 day</option>
                <option value={2}>+ 2 days</option>
                <option value={3}>+ 3 days</option>
                <option value={5}>+ 5 days</option>
                <option value={7}>+ 7 days</option>
              </select>
              {(flexBefore > 0 || flexAfter > 0) && <span className="text-[10px] text-muted-foreground">{flexBefore + flexAfter + 1} days total</span>}
            </div>
          </Card>
        </div>
      </div>

      {/* Quick Links */}
      {flights.length === 0 && (
        <div className="max-w-5xl mx-auto px-4 py-12">
          {pastRoutes.length > 0 && (
            <div className="mb-10">
              <h3 className="text-sm font-medium text-muted-foreground mb-3">Your recent routes</h3>
              <div className="flex flex-wrap gap-2">
                {pastRoutes.map((route) => {
                  const originAirport = AIRPORTS.find((a) => a.code === route.origin);
                  const destAirport = AIRPORTS.find((a) => a.code === route.destination);
                  return (
                    <button
                      key={`${route.origin}-${route.destination}`}
                      onClick={() => { setOrigin(route.origin); setDestination(route.destination); }}
                      className="flex items-center gap-2 px-4 py-2 rounded-full border border-border bg-white dark:bg-slate-900 hover:border-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950/30 transition-all text-sm group"
                    >
                      <span className="font-mono font-semibold text-blue-600">{route.origin}</span>
                      <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                      <span className="font-mono font-semibold text-blue-600">{route.destination}</span>
                      <span className="text-xs text-muted-foreground hidden sm:inline">
                        {originAirport?.city || route.origin} to {destAirport?.city || route.destination}
                      </span>
                      {route.count > 1 && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{route.count}x</Badge>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <h2 className="text-lg font-semibold text-center mb-6 text-muted-foreground">How can we help you today?</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <Link href="/chat">
              <Card className="p-6 h-full hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer group animate-slide-up stagger-1">
                <div className="w-11 h-11 rounded-lg bg-blue-50 dark:bg-blue-900/40 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-sm mb-1.5">AI Travel Assistant</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">Chat with AI to search, book, and manage your flights effortlessly.</p>
              </Card>
            </Link>
            <Link href="/bookings">
              <Card className="p-6 h-full hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer group animate-slide-up stagger-2">
                <div className="w-11 h-11 rounded-lg bg-green-50 dark:bg-green-900/40 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <h3 className="font-semibold text-sm mb-1.5">Manage Bookings</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">View, modify, or cancel your existing reservations anytime.</p>
              </Card>
            </Link>
            <Link href="/loyalty">
              <Card className="p-6 h-full hover:shadow-lg hover:-translate-y-1 transition-all duration-200 cursor-pointer group animate-slide-up stagger-3">
                <div className="w-11 h-11 rounded-lg bg-amber-50 dark:bg-amber-900/40 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-sm mb-1.5">Loyalty Rewards</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">Track miles, tier status, and redeem your reward points.</p>
              </Card>
            </Link>
          </div>

          <div className="mt-10">
            <h3 className="text-sm font-medium text-muted-foreground mb-3">Popular routes</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {POPULAR_ROUTES.map((route) => (
                <button
                  key={`${route.origin}-${route.destination}`}
                  onClick={() => { setOrigin(route.origin); setDestination(route.destination); }}
                  className="p-4 rounded-xl border border-border bg-white dark:bg-slate-900 hover:border-blue-300 hover:shadow-md hover:-translate-y-0.5 transition-all text-left group"
                >
                  <span className="text-lg mb-2 block">{route.emoji}</span>
                  <p className="text-xs font-semibold text-foreground group-hover:text-blue-600 transition-colors">{route.label}</p>
                  <p className="text-[10px] text-muted-foreground mt-1 font-mono">{route.origin} - {route.destination}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="max-w-5xl mx-auto px-4 py-12 flex flex-col items-center gap-3">
          <svg className="w-8 h-8 animate-spin text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
          <p className="text-sm text-muted-foreground">Searching flights...</p>
        </div>
      )}

      {/* Results */}
      {!loading && flights.length > 0 && (
        <div className="max-w-5xl mx-auto px-4 py-8">
          {/* Round-trip tabs */}
          {tripType === "roundtrip" && returnFlights.length > 0 && (
            <div className="flex gap-1 mb-4 p-1 bg-muted rounded-lg w-fit">
              <button
                onClick={() => setActiveTab("outbound")}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === "outbound" ? "bg-white dark:bg-slate-800 shadow-sm text-blue-600" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Outbound · {origin} &rarr; {destination} ({flights.length})
              </button>
              <button
                onClick={() => setActiveTab("return")}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === "return" ? "bg-white dark:bg-slate-800 shadow-sm text-blue-600" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Return · {destination} &rarr; {origin} ({returnFlights.length})
              </button>
            </div>
          )}

          {/* Selected outbound summary (shown when picking return) */}
          {tripType === "roundtrip" && activeTab === "return" && selectedOutbound && (
            <Card className="p-3 mb-4 border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Outbound selected</p>
                    <p className="text-sm font-medium">
                      {selectedOutbound.flight_number} · {selectedOutbound.origin} &rarr; {selectedOutbound.destination} · {new Date(selectedOutbound.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · <span className="text-blue-600">${selectedOutbound.price.toFixed(0)}</span>
                    </p>
                  </div>
                </div>
                <button onClick={() => { setSelectedOutbound(null); setActiveTab("outbound"); }} className="text-xs text-muted-foreground hover:text-foreground underline">Change</button>
              </div>
            </Card>
          )}

          {/* Flexible date price bar */}
          {currentFlexPrices.length > 0 && (
            <div className="mb-5 flex gap-1 overflow-x-auto pb-2">
              {currentFlexPrices.map((fp) => {
                const currentDate = activeTab === "return" ? returnDate : date;
                const isSelected = fp.date === currentDate;
                const dayLabel = new Date(fp.date + "T12:00:00").toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
                return (
                  <button
                    key={fp.date}
                    onClick={() => { if (!isSelected) searchFlights(fp.date, activeTab === "return"); }}
                    className={`flex-1 min-w-[70px] px-2 py-2 rounded-lg border text-center transition-all ${
                      isSelected ? "border-blue-500 bg-blue-50 dark:bg-blue-950/40" : "border-border hover:border-blue-300 hover:bg-muted/50"
                    }`}
                  >
                    <p className={`text-[10px] ${isSelected ? "text-blue-600 font-semibold" : "text-muted-foreground"}`}>{dayLabel}</p>
                    <p className={`text-sm font-semibold ${isSelected ? "text-blue-600" : fp.min_price > 0 ? "text-foreground" : "text-muted-foreground"}`}>
                      {fp.min_price > 0 ? `$${fp.min_price.toFixed(0)}` : "—"}
                    </p>
                  </button>
                );
              })}
            </div>
          )}

          {/* Stops filter + header */}
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold">{filteredFlights.length} flights found</h2>
            <div className="flex items-center gap-2">
              {[null, 0, 1, 2].map((s) => (
                <button
                  key={String(s)}
                  onClick={() => setStopsFilter(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    stopsFilter === s ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {s === null ? "All" : s === 0 ? "Direct" : `${s} Stop${s > 1 ? "s" : ""}`}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            {filteredFlights.map((flight, i) => (
              <Card key={flight.id + i} className="p-5 hover:shadow-lg hover:border-blue-200 dark:hover:border-blue-800 transition-all duration-200 animate-slide-up" style={{ animationDelay: `${i * 0.05}s`, opacity: 0 }}>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div className="flex items-center gap-6">
                    <div className="min-w-[80px]">
                      <p className="font-bold text-base">{flight.flight_number.split("+")[0]}</p>
                      <p className="text-xs font-medium text-muted-foreground">{flight.stops === 0 ? flight.aircraft : `${flight.stops + 1} flights`}</p>
                      <Badge variant="secondary" className="text-[9px] mt-1 px-1.5 py-0">
                        {formatSchedule(flight.days_of_week, flight.valid_from, flight.valid_until)}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-center">
                        <p className="font-semibold text-lg">{new Date(flight.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                        <p className="text-xs font-medium text-muted-foreground">{flight.origin}</p>
                      </div>
                      <div className="flex flex-col items-center gap-0.5 px-2">
                        <div className="flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                          <div className="w-16 h-px bg-gradient-to-r from-blue-400 to-blue-300" />
                          {flight.stops > 0 && (
                            <>
                              {flight.via?.split(",").map((stop, si) => (
                                <span key={si} className="flex items-center gap-1">
                                  <div className="w-2 h-2 rounded-full bg-orange-400 border border-white" title={stop} />
                                  <div className="w-8 h-px bg-gradient-to-r from-orange-300 to-blue-300" />
                                </span>
                              ))}
                            </>
                          )}
                          {flight.stops === 0 && (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-blue-500 -mx-1" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                            </svg>
                          )}
                          <div className="w-16 h-px bg-gradient-to-r from-blue-300 to-blue-400" />
                          <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                        </div>
                        <p className={`text-[10px] ${flight.stops > 0 ? "text-orange-600 font-medium" : "text-muted-foreground"}`}>
                          {flight.stops === 0 ? "Direct" : `${flight.stops} stop${flight.stops > 1 ? "s" : ""} · ${flight.via}`}
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="font-semibold text-lg">{new Date(flight.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                        <p className="text-xs font-medium text-muted-foreground">{flight.destination}</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      {flight.cabin_classes ? (
                        <div className="flex gap-2">
                          {Object.entries(flight.cabin_classes).map(([cls, info]) => (
                            <div key={cls} className="text-center min-w-[70px]">
                              <p className="text-[9px] text-muted-foreground capitalize">{cls.replace("_", " ")}</p>
                              <p className={`text-sm font-bold ${info.available > 0 ? "text-blue-600" : "text-muted-foreground line-through"}`}>${info.price.toFixed(0)}</p>
                              <p className="text-[9px] text-muted-foreground">{info.available} left</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <>
                          <Badge variant="secondary" className="text-[10px] mb-1">{flight.available_seats}/{flight.total_seats} seats</Badge>
                          <p className="text-2xl font-bold text-blue-600">${flight.price.toFixed(0)}</p>
                          <p className="text-[10px] text-muted-foreground">per person</p>
                        </>
                      )}
                    </div>
                    {tripType === "roundtrip" && activeTab === "outbound" ? (
                      <Button size="sm" className="px-5" onClick={() => { setSelectedOutbound(flight); setActiveTab("return"); }}>Select</Button>
                    ) : tripType === "roundtrip" && activeTab === "return" && selectedOutbound ? (
                      <Link href={`/book/${selectedOutbound.id}?date=${date}&returnFlight=${flight.id}&returnDate=${returnDate}`}>
                        <Button size="sm" className="px-5">Select</Button>
                      </Link>
                    ) : (
                      <Link href={`/book/${flight.id}${date ? `?date=${date}` : ""}`}>
                        <Button size="sm" className="px-5">Select</Button>
                      </Link>
                    )}
                  </div>
                </div>
                {/* Expandable segment details for multi-stop */}
                {flight.stops > 0 && flight.segments && (
                  <>
                    <button
                      type="button"
                      onClick={() => setExpandedFlight(expandedFlight === flight.id ? null : flight.id)}
                      className="mt-3 text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className={`w-3 h-3 transition-transform ${expandedFlight === flight.id ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                      {expandedFlight === flight.id ? "Hide" : "View"} flight details
                    </button>
                    {expandedFlight === flight.id && (
                      <div className="mt-3 pt-3 border-t border-border space-y-2">
                        {flight.segments.map((seg, si) => {
                          const layover = si < flight.segments!.length - 1
                            ? Math.round((new Date(flight.segments![si + 1].dep).getTime() - new Date(seg.arr).getTime()) / 60000)
                            : null;
                          return (
                            <div key={si}>
                              <div className="flex items-center gap-4 p-2 rounded-md bg-muted/40">
                                <div className="w-16 text-center">
                                  <p className="text-xs font-bold">{seg.flight}</p>
                                </div>
                                <div className="flex-1 flex items-center gap-3">
                                  <div>
                                    <p className="text-sm font-semibold">{new Date(seg.dep).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                                    <p className="text-[10px] text-muted-foreground">{seg.from}</p>
                                  </div>
                                  <div className="flex-1 flex items-center gap-1">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                                    <div className="flex-1 h-px bg-blue-200" />
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-blue-500" viewBox="0 0 24 24" fill="currentColor">
                                      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                                    </svg>
                                    <div className="flex-1 h-px bg-blue-200" />
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                                  </div>
                                  <div>
                                    <p className="text-sm font-semibold">{new Date(seg.arr).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                                    <p className="text-[10px] text-muted-foreground">{seg.to}</p>
                                  </div>
                                </div>
                                <p className="text-xs font-medium text-blue-600">${seg.price.toFixed(0)}</p>
                              </div>
                              {layover !== null && (
                                <div className="flex items-center gap-2 py-1.5 pl-20">
                                  <div className="w-px h-4 bg-orange-300" />
                                  <p className="text-[10px] text-orange-600 font-medium">
                                    {Math.floor(layover / 60)}h {layover % 60}m layover in {seg.to}
                                  </p>
                                </div>
                              )}
                            </div>
                          );
                        })}
                        <div className="flex justify-between text-xs pt-1 text-muted-foreground">
                          <span>Total travel time: {(() => { const mins = Math.round((new Date(flight.arrival).getTime() - new Date(flight.departure).getTime()) / 60000); return `${Math.floor(mins/60)}h ${mins%60}m`; })()}</span>
                          <span>{flight.segments.length} flights · {flight.stops} stop{flight.stops > 1 ? "s" : ""}</span>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
