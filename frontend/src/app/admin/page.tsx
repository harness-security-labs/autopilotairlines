"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Stats {
  users: number;
  bookings: number;
  mcp_tools: number;
  active_conversations: number;
}

interface AdminFlight {
  id: string;
  flight_number: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  status: string;
  aircraft: string;
  available_seats: number;
  total_seats: number;
  days_of_week: string | null;
}

interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  loyalty_tier: string;
}

interface OfferConditions {
  max_uses_total?: number;
  max_uses_per_user?: number;
  new_user?: boolean;
  min_bookings_last_n_days?: { min_bookings: number; days: number };
  loyalty_tier_min?: string;
  cabin_class?: string[];
  min_booking_value?: number;
  keywords?: string[];
  routes?: { origin: string; destination: string }[];
}

interface AdminOffer {
  code: string;
  discount_percent: number;
  description: string;
  valid_from?: string | null;
  valid_until?: string | null;
  conditions?: OfferConditions;
}

const TIER_COLORS: Record<string, string> = {
  bronze: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  silver: "bg-slate-100 text-slate-700 dark:bg-slate-800/40 dark:text-slate-300",
  gold: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  platinum: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
};

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [activeTab, setActiveTab] = useState("flights");

  const [flights, setFlights] = useState<AdminFlight[]>([]);
  const [flightsLoading, setFlightsLoading] = useState(false);
  const [flightSearch, setFlightSearch] = useState("");
  const [flightTotal, setFlightTotal] = useState(0);
  const [flightTotalPages, setFlightTotalPages] = useState(1);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userSearch, setUserSearch] = useState("");
  const [userRole, setUserRole] = useState("");
  const [userTier, setUserTier] = useState("");
  const [userTotal, setUserTotal] = useState(0);
  const [userTotalPages, setUserTotalPages] = useState(1);

  const [adminOffers, setAdminOffers] = useState<AdminOffer[]>([]);
  const [systemOffers, setSystemOffers] = useState<{ code: string; discount_percent: number; description: string; type: string }[]>([]);
  const [offersLoaded, setOffersLoaded] = useState(false);

  const [cancelDialog, setCancelDialog] = useState<AdminFlight | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);

  const [rescheduleDialog, setRescheduleDialog] = useState<AdminFlight | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduleDep, setRescheduleDep] = useState("");
  const [rescheduleArr, setRescheduleArr] = useState("");
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [rescheduleLoading, setRescheduleLoading] = useState(false);

  const [offerDialog, setOfferDialog] = useState(false);
  const [offerCode, setOfferCode] = useState("");
  const [offerDiscount, setOfferDiscount] = useState("");
  const [offerDesc, setOfferDesc] = useState("");
  const [offerFrom, setOfferFrom] = useState("");
  const [offerUntil, setOfferUntil] = useState("");
  const [offerLoading, setOfferLoading] = useState(false);
  const [condMaxTotal, setCondMaxTotal] = useState("");
  const [condMaxPerUser, setCondMaxPerUser] = useState("");
  const [condNewUser, setCondNewUser] = useState(false);
  const [condMinBookings, setCondMinBookings] = useState("");
  const [condMinBookingsDays, setCondMinBookingsDays] = useState("30");
  const [condLoyaltyTier, setCondLoyaltyTier] = useState("");
  const [condCabinClass, setCondCabinClass] = useState<string[]>([]);
  const [condMinValue, setCondMinValue] = useState("");
  const [condKeywords, setCondKeywords] = useState("");

  const [creditDialog, setCreditDialog] = useState<AdminUser | null>(null);
  const [creditPoints, setCreditPoints] = useState("");
  const [creditReason, setCreditReason] = useState("");
  const [creditLoading, setCreditLoading] = useState(false);

  const [tierDialog, setTierDialog] = useState<AdminUser | null>(null);
  const [newTier, setNewTier] = useState("");
  const [tierLoading, setTierLoading] = useState(false);

  const [flightPage, setFlightPage] = useState(1);
  const [userPage, setUserPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/api/v1/admin/stats`, { headers })
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [flightStatus, setFlightStatus] = useState("");

  const fetchFlights = () => {
    if (!token) return;
    setFlightsLoading(true);
    const params = new URLSearchParams({ page: String(flightPage), page_size: String(pageSize) });
    if (flightSearch) params.set("search", flightSearch);
    if (flightStatus) params.set("status", flightStatus);
    fetch(`${API_URL}/api/v1/admin/flights?${params}`, { headers })
      .then((r) => r.json())
      .then((d) => { setFlights(d.items || []); setFlightTotal(d.total || 0); setFlightTotalPages(d.total_pages || 1); })
      .catch(() => {})
      .finally(() => setFlightsLoading(false));
  };

  const fetchUsers = () => {
    if (!token) return;
    setUsersLoading(true);
    const params = new URLSearchParams({ page: String(userPage), page_size: String(pageSize) });
    if (userSearch) params.set("search", userSearch);
    if (userRole) params.set("role", userRole);
    if (userTier) params.set("tier", userTier);
    fetch(`${API_URL}/api/v1/admin/users?${params}`, { headers })
      .then((r) => r.json())
      .then((d) => { setUsers(d.items || []); setUserTotal(d.total || 0); setUserTotalPages(d.total_pages || 1); })
      .catch(() => {})
      .finally(() => setUsersLoading(false));
  };

  useEffect(() => {
    if (activeTab === "flights") fetchFlights();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, flightPage, flightSearch, flightStatus, pageSize]);

  useEffect(() => {
    if (activeTab === "users") fetchUsers();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, userPage, userSearch, userRole, userTier, pageSize]);

  useEffect(() => {
    if (!token) return;
    if (activeTab === "offers" && !offersLoaded) {
      Promise.all([
        fetch(`${API_URL}/api/v1/admin/offers`, { headers }).then((r) => r.json()),
        fetch(`${API_URL}/api/v1/bookings/coupons/available`).then((r) => r.json()),
      ]).then(([admin, system]) => {
        setAdminOffers(admin.offers || []);
        setSystemOffers(system.offers || []);
        setOffersLoaded(true);
      }).catch(() => {});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const handleCancelFlight = async () => {
    if (!cancelDialog) return;
    setCancelLoading(true);
    const res = await fetch(`${API_URL}/api/v1/admin/flights/${cancelDialog.id}/cancel`, {
      method: "POST",
      headers,
      body: JSON.stringify({ reason: cancelReason || null }),
    });
    const data = await res.json();
    setCancelLoading(false);
    setCancelDialog(null);
    setCancelReason("");
    if (res.ok) {
      showToast(`Flight ${data.flight_number} cancelled. ${data.affected_bookings} booking(s) notified.`);
      fetchFlights();
    } else {
      showToast(data.detail || "Failed to cancel flight", "error");
    }
  };

  const handleReschedule = async () => {
    if (!rescheduleDialog) return;
    setRescheduleLoading(true);
    const isRecurring = !!rescheduleDialog.days_of_week;
    const url = isRecurring
      ? `${API_URL}/api/v1/admin/flights/${rescheduleDialog.id}/override-schedule`
      : `${API_URL}/api/v1/admin/flights/${rescheduleDialog.id}/reschedule`;
    const method = isRecurring ? "POST" : "PUT";
    const body = isRecurring
      ? { date: rescheduleDate, new_departure: rescheduleDep, new_arrival: rescheduleArr, reason: rescheduleReason || null }
      : { new_departure: rescheduleDep, new_arrival: rescheduleArr, reason: rescheduleReason || null };

    const res = await fetch(url, { method, headers, body: JSON.stringify(body) });
    const data = await res.json();
    setRescheduleLoading(false);
    setRescheduleDialog(null);
    setRescheduleDate("");
    setRescheduleDep("");
    setRescheduleArr("");
    setRescheduleReason("");
    if (res.ok) {
      showToast(`Flight rescheduled successfully. ${data.affected_bookings} booking(s) updated.`);
      fetchFlights();
    } else {
      showToast(data.detail || "Failed to reschedule", "error");
    }
  };

  const handleCreateOffer = async () => {
    setOfferLoading(true);
    const conditions: Record<string, unknown> = {};
    if (condMaxTotal) conditions.max_uses_total = parseInt(condMaxTotal);
    if (condMaxPerUser) conditions.max_uses_per_user = parseInt(condMaxPerUser);
    if (condNewUser) conditions.new_user = true;
    if (condMinBookings) conditions.min_bookings_last_n_days = { min_bookings: parseInt(condMinBookings), days: parseInt(condMinBookingsDays) || 30 };
    if (condLoyaltyTier) conditions.loyalty_tier_min = condLoyaltyTier;
    if (condCabinClass.length > 0) conditions.cabin_class = condCabinClass;
    if (condMinValue) conditions.min_booking_value = parseFloat(condMinValue);
    if (condKeywords.trim()) conditions.keywords = condKeywords.split(",").map(k => k.trim()).filter(Boolean);

    const res = await fetch(`${API_URL}/api/v1/admin/offers`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        code: offerCode.toUpperCase(),
        discount_percent: parseInt(offerDiscount),
        description: offerDesc,
        valid_from: offerFrom || null,
        valid_until: offerUntil || null,
        conditions: Object.keys(conditions).length > 0 ? conditions : null,
      }),
    });
    const data = await res.json();
    setOfferLoading(false);
    if (res.ok) {
      setAdminOffers([...adminOffers, data]);
      setOfferDialog(false);
      setOfferCode("");
      setOfferDiscount("");
      setOfferDesc("");
      setOfferFrom("");
      setOfferUntil("");
      setCondMaxTotal("");
      setCondMaxPerUser("");
      setCondNewUser(false);
      setCondMinBookings("");
      setCondMinBookingsDays("30");
      setCondLoyaltyTier("");
      setCondCabinClass([]);
      setCondMinValue("");
      setCondKeywords("");
      showToast(`Offer "${data.code}" created successfully`);
    } else {
      showToast(data.detail || "Failed to create offer", "error");
    }
  };

  const handleCreditPoints = async () => {
    if (!creditDialog) return;
    setCreditLoading(true);
    const res = await fetch(`${API_URL}/api/v1/admin/users/${creditDialog.id}/credit-points`, {
      method: "POST",
      headers,
      body: JSON.stringify({ points: parseInt(creditPoints), reason: creditReason }),
    });
    const data = await res.json();
    setCreditLoading(false);
    setCreditDialog(null);
    setCreditPoints("");
    setCreditReason("");
    if (res.ok) {
      showToast(`Credited ${data.points_credited.toLocaleString()} pts to ${creditDialog.name}. Balance: ${data.new_balance.toLocaleString()}`);
    } else {
      showToast(data.detail || "Failed to credit points", "error");
    }
  };

  const handleTierUpdate = async () => {
    if (!tierDialog) return;
    setTierLoading(true);
    const res = await fetch(`${API_URL}/api/v1/admin/users/${tierDialog.id}/tier`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ tier: newTier }),
    });
    const data = await res.json();
    setTierLoading(false);
    setTierDialog(null);
    setNewTier("");
    if (res.ok) {
      showToast(`Tier updated: ${data.previous_tier} → ${data.new_tier}`);
      fetchUsers();
    } else {
      showToast(data.detail || "Failed to update tier", "error");
    }
  };

  const scheduledCount = flights.filter((f) => f.status === "scheduled").length;
  const cancelledCount = flights.filter((f) => f.status === "cancelled").length;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-sm font-medium animate-fade-in border ${
          toast.type === "success"
            ? "bg-green-50 dark:bg-green-950/80 text-green-800 dark:text-green-200 border-green-200 dark:border-green-800"
            : "bg-red-50 dark:bg-red-950/80 text-red-800 dark:text-red-200 border-red-200 dark:border-red-800"
        }`}>
          <span className={`w-2 h-2 rounded-full shrink-0 ${toast.type === "success" ? "bg-green-500" : "bg-red-500"}`} />
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold">Admin Dashboard</h1>
            <p className="text-sm text-muted-foreground">Manage flights, offers, and users</p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card className="p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-16 h-16 bg-blue-500/5 rounded-bl-[40px]" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Users</p>
              <p className="text-2xl font-bold">{stats?.users ?? "---"}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-16 h-16 bg-green-500/5 rounded-bl-[40px]" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Bookings</p>
              <p className="text-2xl font-bold">{stats?.bookings ?? "---"}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-16 h-16 bg-amber-500/5 rounded-bl-[40px]" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Flights</p>
              <p className="text-2xl font-bold">{flightTotal || (stats?.mcp_tools ?? "---")}</p>
              {flightTotal > 0 && <p className="text-[10px] text-muted-foreground">{scheduledCount} active, {cancelledCount} cancelled</p>}
            </div>
          </div>
        </Card>
        <Card className="p-5 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-16 h-16 bg-purple-500/5 rounded-bl-[40px]" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
            </div>
            <div>
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Offers</p>
              <p className="text-2xl font-bold">{offersLoaded ? adminOffers.length + systemOffers.length : "---"}</p>
              {offersLoaded && <p className="text-[10px] text-muted-foreground">{adminOffers.length} campaigns</p>}
            </div>
          </div>
        </Card>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center justify-between mb-6 border-b border-border pb-4">
        <div className="flex items-center gap-1 bg-muted p-1 rounded-lg">
          {([
            { key: "flights", label: "Flights", icon: "M12 19l9 2-9-18-9 18 9-2zm0 0v-8" },
            { key: "offers", label: "Offers", icon: "M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" },
            { key: "users", label: "Users", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
          ]).map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d={tab.icon} />
              </svg>
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {activeTab === "flights" && (
            <>
              <select
                value={flightStatus}
                onChange={(e) => { setFlightStatus(e.target.value); setFlightPage(1); }}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="">All Status</option>
                <option value="scheduled">Scheduled</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <Input placeholder="Search flights..." value={flightSearch} onChange={(e) => { setFlightSearch(e.target.value); setFlightPage(1); }} className="w-48" />
            </>
          )}
          {activeTab === "offers" && (
            <Button onClick={() => setOfferDialog(true)}>
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Create Offer
            </Button>
          )}
          {activeTab === "users" && (
            <>
              <select
                value={userRole}
                onChange={(e) => { setUserRole(e.target.value); setUserPage(1); }}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="">All Roles</option>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              <select
                value={userTier}
                onChange={(e) => { setUserTier(e.target.value); setUserPage(1); }}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="">All Tiers</option>
                <option value="bronze">Bronze</option>
                <option value="silver">Silver</option>
                <option value="gold">Gold</option>
                <option value="platinum">Platinum</option>
              </select>
              <Input placeholder="Search users..." value={userSearch} onChange={(e) => { setUserSearch(e.target.value); setUserPage(1); }} className="w-48" />
            </>
          )}
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(parseInt(e.target.value)); setFlightPage(1); setUserPage(1); }}
            className="h-9 rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="5">5 / page</option>
            <option value="10">10 / page</option>
            <option value="25">25 / page</option>
            <option value="50">50 / page</option>
          </select>
        </div>
      </div>

      {/* Tab Content */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as string)}>
        <TabsList className="hidden">
          <TabsTrigger value="flights">Flights</TabsTrigger>
          <TabsTrigger value="offers">Offers</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
        </TabsList>

        {/* Flights Tab */}
        <TabsContent value="flights">
          <div className="space-y-3">

            {flightsLoading && (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-16 bg-muted/50 rounded-xl animate-pulse" />
                ))}
              </div>
            )}

            {!flightsLoading && flights.length === 0 && (
              <Card className="p-8 text-center">
                <p className="text-muted-foreground text-sm">No flights match your search</p>
              </Card>
            )}

            <div className="space-y-2">
              {flights.map((f) => (
                <Card key={f.id} className={`p-4 transition-all hover:shadow-md ${f.status === "cancelled" ? "opacity-60" : ""}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0 flex-1">
                      <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                        <svg xmlns="http://www.w3.org/2000/svg" className={`w-5 h-5 ${f.status === "cancelled" ? "text-red-500" : "text-blue-600"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                        </svg>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-mono font-bold">{f.flight_number}</span>
                          <Badge variant={f.status === "cancelled" ? "destructive" : "secondary"} className="text-[9px]">
                            {f.status}
                          </Badge>
                          {f.days_of_week && (
                            <Badge className="text-[9px] bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">Recurring</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-sm">{f.origin}</span>
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                          </svg>
                          <span className="text-sm">{f.destination}</span>
                          <span className="text-xs text-muted-foreground hidden sm:inline ml-2">{f.aircraft}</span>
                        </div>
                      </div>
                      <div className="text-right hidden sm:block shrink-0">
                        <p className="text-sm font-medium">{new Date(f.departure).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(f.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} - {new Date(f.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>
                    {f.status !== "cancelled" && (
                      <div className="flex items-center gap-2 ml-4 shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs"
                          onClick={() => setRescheduleDialog(f)}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Reschedule
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="text-xs"
                          onClick={() => setCancelDialog(f)}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {flightTotalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-border">
                <p className="text-xs text-muted-foreground">{flightTotal} flights total</p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" className="text-xs h-7 w-7 p-0" disabled={flightPage <= 1} onClick={() => setFlightPage(flightPage - 1)}>
                    &lsaquo;
                  </Button>
                  {Array.from({ length: Math.min(flightTotalPages, 5) }, (_, i) => {
                    let p: number;
                    if (flightTotalPages <= 5) p = i + 1;
                    else if (flightPage <= 3) p = i + 1;
                    else if (flightPage >= flightTotalPages - 2) p = flightTotalPages - 4 + i;
                    else p = flightPage - 2 + i;
                    return (
                      <Button key={p} variant={p === flightPage ? "default" : "outline"} size="sm" className="text-xs h-7 w-7 p-0" onClick={() => setFlightPage(p)}>
                        {p}
                      </Button>
                    );
                  })}
                  <Button variant="outline" size="sm" className="text-xs h-7 w-7 p-0" disabled={flightPage >= flightTotalPages} onClick={() => setFlightPage(flightPage + 1)}>
                    &rsaquo;
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Offers Tab */}
        <TabsContent value="offers">
          <div className="space-y-6">

            {/* Admin Campaigns */}
            {adminOffers.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Your Campaigns</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {adminOffers.map((o) => (
                    <Card key={o.code} className="p-4 border-2 border-dashed border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/20">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-base font-bold text-blue-700 dark:text-blue-300">{o.code}</span>
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300">
                              {o.discount_percent}% off
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">{o.description}</p>
                        </div>
                      </div>
                      {(o.valid_from || o.valid_until) && (
                        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-blue-200/50 dark:border-blue-800/50">
                          {o.valid_from && (
                            <span className="text-[10px] text-muted-foreground">From: <span className="font-medium">{o.valid_from}</span></span>
                          )}
                          {o.valid_until && (
                            <span className="text-[10px] text-muted-foreground">Until: <span className="font-medium">{o.valid_until}</span></span>
                          )}
                        </div>
                      )}
                      {o.conditions && Object.keys(o.conditions).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {o.conditions.max_uses_total && <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">{o.conditions.max_uses_total} uses max</span>}
                          {o.conditions.max_uses_per_user && <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">{o.conditions.max_uses_per_user}/user</span>}
                          {o.conditions.new_user && <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">New users</span>}
                          {o.conditions.loyalty_tier_min && <span className="text-[9px] px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300">{o.conditions.loyalty_tier_min}+</span>}
                          {o.conditions.cabin_class && <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300">{o.conditions.cabin_class.join(", ")}</span>}
                          {o.conditions.keywords && <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300">{o.conditions.keywords.join(", ")}</span>}
                          {o.conditions.min_booking_value && <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">${o.conditions.min_booking_value}+ value</span>}
                          {o.conditions.min_bookings_last_n_days && <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300">{o.conditions.min_bookings_last_n_days.min_bookings}+ bookings/{o.conditions.min_bookings_last_n_days.days}d</span>}
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {adminOffers.length === 0 && offersLoaded && (
              <Card className="p-8 text-center border-dashed">
                <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-muted flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                  </svg>
                </div>
                <p className="text-sm text-muted-foreground">No campaigns yet. Create your first offer to get started.</p>
              </Card>
            )}

            {/* System Offers */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Active System Offers</p>
              <Card className="p-0 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/30">
                      <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground">Code</th>
                      <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground">Description</th>
                      <th className="text-left py-2.5 px-4 text-xs font-medium text-muted-foreground">Type</th>
                      <th className="text-right py-2.5 px-4 text-xs font-medium text-muted-foreground">Discount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {systemOffers.map((o) => (
                      <tr key={o.code} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="py-2.5 px-4 font-mono font-medium text-xs">{o.code}</td>
                        <td className="py-2.5 px-4 text-xs text-muted-foreground">{o.description}</td>
                        <td className="py-2.5 px-4">
                          <Badge variant="secondary" className="text-[9px] capitalize">{o.type}</Badge>
                        </td>
                        <td className="py-2.5 px-4 text-right font-semibold text-xs text-green-600">{o.discount_percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users">
          <div className="space-y-3">

            {usersLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-muted/50 rounded-xl animate-pulse" />
                ))}
              </div>
            )}

            <div className="space-y-2">
              {users.map((u) => (
                <Card key={u.id} className="p-4 transition-all hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shrink-0">
                        <span className="text-sm font-bold text-white">{u.name.charAt(0).toUpperCase()}</span>
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium">{u.name}</span>
                          {u.role === "admin" && (
                            <Badge className="text-[9px] bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">Admin</Badge>
                          )}
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium capitalize ${TIER_COLORS[u.loyalty_tier] || "bg-muted text-muted-foreground"}`}>
                            {u.loyalty_tier}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4 shrink-0">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() => setCreditDialog(u)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Credit Points
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() => { setTierDialog(u); setNewTier(u.loyalty_tier); }}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                        </svg>
                        Upgrade Tier
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>

            {/* Pagination */}
            {userTotalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-border">
                <p className="text-xs text-muted-foreground">{userTotal} users total</p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" className="text-xs h-7 w-7 p-0" disabled={userPage <= 1} onClick={() => setUserPage(userPage - 1)}>
                    &lsaquo;
                  </Button>
                  {Array.from({ length: Math.min(userTotalPages, 5) }, (_, i) => {
                    let p: number;
                    if (userTotalPages <= 5) p = i + 1;
                    else if (userPage <= 3) p = i + 1;
                    else if (userPage >= userTotalPages - 2) p = userTotalPages - 4 + i;
                    else p = userPage - 2 + i;
                    return (
                      <Button key={p} variant={p === userPage ? "default" : "outline"} size="sm" className="text-xs h-7 w-7 p-0" onClick={() => setUserPage(p)}>
                        {p}
                      </Button>
                    );
                  })}
                  <Button variant="outline" size="sm" className="text-xs h-7 w-7 p-0" disabled={userPage >= userTotalPages} onClick={() => setUserPage(userPage + 1)}>
                    &rsaquo;
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Cancel Flight Dialog */}
      <Dialog open={!!cancelDialog} onOpenChange={(open) => { if (!open) setCancelDialog(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Flight</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono font-bold text-sm">{cancelDialog?.flight_number}</span>
                {cancelDialog?.days_of_week && <Badge className="text-[9px] bg-blue-100 text-blue-700">Recurring</Badge>}
              </div>
              <p className="text-xs text-muted-foreground">{cancelDialog?.origin} → {cancelDialog?.destination}</p>
              <p className="text-xs text-muted-foreground">{cancelDialog && new Date(cancelDialog.departure).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</p>
            </div>
            <p className="text-sm text-muted-foreground">
              This will cancel the flight and notify all affected passengers. Bookings will be automatically cancelled and refunds initiated.
            </p>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Reason (optional)</label>
              <Input value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} placeholder="e.g. Severe weather conditions" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelDialog(null)}>Keep Flight</Button>
            <Button variant="destructive" disabled={cancelLoading} onClick={handleCancelFlight}>
              {cancelLoading ? "Cancelling..." : "Cancel Flight"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reschedule Dialog */}
      <Dialog open={!!rescheduleDialog} onOpenChange={(open) => { if (!open) setRescheduleDialog(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reschedule Flight</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono font-bold text-sm">{rescheduleDialog?.flight_number}</span>
                {rescheduleDialog?.days_of_week ? (
                  <Badge className="text-[9px] bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">Recurring — day-specific override</Badge>
                ) : (
                  <Badge variant="secondary" className="text-[9px]">One-off</Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{rescheduleDialog?.origin} → {rescheduleDialog?.destination}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Current: {rescheduleDialog && new Date(rescheduleDialog.departure).toLocaleString()} — {rescheduleDialog && new Date(rescheduleDialog.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
            {rescheduleDialog?.days_of_week && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Date to override</label>
                <Input type="date" value={rescheduleDate} onChange={(e) => setRescheduleDate(e.target.value)} />
                <p className="text-[10px] text-muted-foreground mt-1">Only this specific date will be affected. Other days remain unchanged.</p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">New Departure</label>
                <Input type="datetime-local" value={rescheduleDep} onChange={(e) => setRescheduleDep(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">New Arrival</label>
                <Input type="datetime-local" value={rescheduleArr} onChange={(e) => setRescheduleArr(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Reason (optional)</label>
              <Input value={rescheduleReason} onChange={(e) => setRescheduleReason(e.target.value)} placeholder="e.g. Runway maintenance at origin airport" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRescheduleDialog(null)}>Cancel</Button>
            <Button
              disabled={rescheduleLoading || !rescheduleDep || !rescheduleArr || (!!rescheduleDialog?.days_of_week && !rescheduleDate)}
              onClick={handleReschedule}
            >
              {rescheduleLoading ? "Saving..." : "Confirm Reschedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Offer Dialog */}
      <Dialog open={offerDialog} onOpenChange={setOfferDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Offer</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Promo Code</label>
              <Input value={offerCode} onChange={(e) => setOfferCode(e.target.value.toUpperCase())} placeholder="e.g. SUMMER30" className="uppercase font-mono" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Discount %</label>
                <Input type="number" min="1" max="100" value={offerDiscount} onChange={(e) => setOfferDiscount(e.target.value)} placeholder="30" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Preview</label>
                <div className="h-9 rounded-md border border-input bg-muted/30 flex items-center justify-center">
                  <span className="text-sm font-bold text-green-600">{offerDiscount ? `${offerDiscount}% off` : "---"}</span>
                </div>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Description</label>
              <Input value={offerDesc} onChange={(e) => setOfferDesc(e.target.value)} placeholder="e.g. Summer campaign — 30% off all flights" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Valid From</label>
                <Input type="date" value={offerFrom} onChange={(e) => setOfferFrom(e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Valid Until</label>
                <Input type="date" value={offerUntil} onChange={(e) => setOfferUntil(e.target.value)} />
              </div>
            </div>
            <details className="pt-2 border-t border-border">
              <summary className="text-xs font-medium text-muted-foreground cursor-pointer py-1">Conditions (optional)</summary>
              <div className="space-y-3 mt-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Max Total Uses</label>
                    <Input type="number" min="1" value={condMaxTotal} onChange={(e) => setCondMaxTotal(e.target.value)} placeholder="e.g. 100" />
                  </div>
                  <div>
                    <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Max Uses Per User</label>
                    <Input type="number" min="1" value={condMaxPerUser} onChange={(e) => setCondMaxPerUser(e.target.value)} placeholder="e.g. 1" />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="cond-new-user" checked={condNewUser} onChange={(e) => setCondNewUser(e.target.checked)} className="rounded" />
                  <label htmlFor="cond-new-user" className="text-xs">New users only (no prior bookings)</label>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Min Bookings Required</label>
                    <Input type="number" min="1" value={condMinBookings} onChange={(e) => setCondMinBookings(e.target.value)} placeholder="e.g. 3" />
                  </div>
                  <div>
                    <label className="text-[10px] font-medium text-muted-foreground mb-1 block">In Last N Days</label>
                    <Input type="number" min="1" value={condMinBookingsDays} onChange={(e) => setCondMinBookingsDays(e.target.value)} placeholder="30" />
                  </div>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Min Loyalty Tier</label>
                  <select value={condLoyaltyTier} onChange={(e) => setCondLoyaltyTier(e.target.value)} className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="">Any tier</option>
                    <option value="silver">Silver+</option>
                    <option value="gold">Gold+</option>
                    <option value="platinum">Platinum</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Cabin Classes</label>
                  <div className="flex gap-3">
                    {(["economy", "premium_economy", "business"] as const).map(cls => (
                      <label key={cls} className="flex items-center gap-1 text-xs">
                        <input type="checkbox" checked={condCabinClass.includes(cls)} onChange={(e) => setCondCabinClass(e.target.checked ? [...condCabinClass, cls] : condCabinClass.filter(c => c !== cls))} className="rounded" />
                        {cls.replace("_", " ")}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Min Booking Value ($)</label>
                  <Input type="number" min="1" value={condMinValue} onChange={(e) => setCondMinValue(e.target.value)} placeholder="e.g. 500" />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground mb-1 block">Keywords (comma-separated, matches flight/route)</label>
                  <Input value={condKeywords} onChange={(e) => setCondKeywords(e.target.value)} placeholder="e.g. JFK, LAX, AA101" />
                </div>
              </div>
            </details>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOfferDialog(false)}>Cancel</Button>
            <Button
              disabled={offerLoading || !offerCode.trim() || !offerDiscount || !offerDesc.trim()}
              onClick={handleCreateOffer}
            >
              {offerLoading ? "Creating..." : "Create Offer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Credit Points Dialog */}
      <Dialog open={!!creditDialog} onOpenChange={(open) => { if (!open) setCreditDialog(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Credit Loyalty Points</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 border border-border">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shrink-0">
                <span className="text-sm font-bold text-white">{creditDialog?.name.charAt(0).toUpperCase()}</span>
              </div>
              <div>
                <p className="text-sm font-medium">{creditDialog?.name}</p>
                <p className="text-xs text-muted-foreground">{creditDialog?.email}</p>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Points to credit</label>
              <Input type="number" min="1" value={creditPoints} onChange={(e) => setCreditPoints(e.target.value)} placeholder="e.g. 5000" />
              {creditPoints && parseInt(creditPoints) > 0 && (
                <p className="text-[10px] text-muted-foreground mt-1">Worth ${(parseInt(creditPoints) * 0.01).toFixed(2)}</p>
              )}
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Reason</label>
              <Input value={creditReason} onChange={(e) => setCreditReason(e.target.value)} placeholder="e.g. Compensation for delayed flight AP3421" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreditDialog(null)}>Cancel</Button>
            <Button
              disabled={creditLoading || !creditPoints || parseInt(creditPoints) <= 0 || !creditReason.trim()}
              onClick={handleCreditPoints}
            >
              {creditLoading ? "Crediting..." : `Credit ${creditPoints ? parseInt(creditPoints).toLocaleString() : "0"} Points`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upgrade Tier Dialog */}
      <Dialog open={!!tierDialog} onOpenChange={(open) => { if (!open) setTierDialog(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Loyalty Tier</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 border border-border">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shrink-0">
                <span className="text-sm font-bold text-white">{tierDialog?.name.charAt(0).toUpperCase()}</span>
              </div>
              <div>
                <p className="text-sm font-medium">{tierDialog?.name}</p>
                <p className="text-xs text-muted-foreground">{tierDialog?.email}</p>
              </div>
              <span className={`ml-auto inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium capitalize ${TIER_COLORS[tierDialog?.loyalty_tier || "bronze"]}`}>
                {tierDialog?.loyalty_tier}
              </span>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Select New Tier</label>
              <div className="grid grid-cols-4 gap-2">
                {(["bronze", "silver", "gold", "platinum"] as const).map((tier) => (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => setNewTier(tier)}
                    className={`p-3 rounded-lg border-2 text-center transition-all ${
                      newTier === tier
                        ? "border-blue-600 bg-blue-50 dark:bg-blue-950/30"
                        : "border-border hover:border-blue-300"
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full mx-auto mb-1.5 ${
                      tier === "bronze" ? "bg-amber-700" : tier === "silver" ? "bg-slate-400" : tier === "gold" ? "bg-yellow-500" : "bg-gradient-to-r from-slate-600 to-slate-800"
                    }`} />
                    <p className="text-xs font-medium capitalize">{tier}</p>
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTierDialog(null)}>Cancel</Button>
            <Button
              disabled={tierLoading || newTier === tierDialog?.loyalty_tier}
              onClick={handleTierUpdate}
            >
              {tierLoading ? "Updating..." : "Update Tier"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
