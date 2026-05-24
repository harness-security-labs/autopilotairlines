"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LoyaltyData {
  points: number;
  points_earned_12m: number;
  points_value: number;
  tier: string;
  tier_expiry: string | null;
}

interface Transaction {
  id: string;
  points: number;
  transaction_type: string;
  source: string;
  created_at: string;
}

const TIER_ORDER = ["bronze", "silver", "gold", "platinum"];
const TIER_THRESHOLDS: Record<string, number> = {
  bronze: 0,
  silver: 25000,
  gold: 50000,
  platinum: 100000,
};

const TIER_COLORS: Record<string, string> = {
  bronze: "bg-amber-700",
  silver: "bg-slate-400",
  gold: "bg-yellow-500",
  platinum: "bg-gradient-to-r from-slate-600 to-slate-800",
};

const TIER_TEXT_COLORS: Record<string, string> = {
  bronze: "text-amber-700",
  silver: "text-slate-500",
  gold: "text-yellow-600",
  platinum: "text-slate-700",
};

const TIER_BENEFITS: { tier: string; benefits: string[] }[] = [
  {
    tier: "bronze",
    benefits: [
      "Earn 10 pts per $1 spent",
      "Base baggage allowance",
      "Online check-in",
    ],
  },
  {
    tier: "silver",
    benefits: [
      "All Bronze benefits",
      "+5kg per checked bag",
      "Priority check-in",
      "Seat selection included",
    ],
  },
  {
    tier: "gold",
    benefits: [
      "All Silver benefits",
      "+1 extra checked bag",
      "+5kg per bag, +3kg carry-on",
      "Lounge access (international)",
      "Priority boarding",
      "Free seat upgrades (subject to availability)",
    ],
  },
  {
    tier: "platinum",
    benefits: [
      "All Gold benefits",
      "+1 extra checked bag",
      "+10kg per bag, +3kg carry-on",
      "Lounge access (all flights)",
      "Complimentary upgrade to next cabin",
      "Dedicated support line",
      "Guaranteed seat on full flights",
    ],
  },
];

export default function LoyaltyPage() {
  const [data, setData] = useState<LoyaltyData | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    setIsLoggedIn(true);
    fetch(`${API_URL}/api/v1/loyalty/balance`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));

    fetch(`${API_URL}/api/v1/loyalty/transactions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((d) => setTransactions(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, []);

  const currentTierIdx = data ? TIER_ORDER.indexOf(data.tier) : 0;
  const nextTier = currentTierIdx < TIER_ORDER.length - 1 ? TIER_ORDER[currentTierIdx + 1] : null;
  const nextTierThreshold = nextTier ? TIER_THRESHOLDS[nextTier] : 0;
  const currentTierThreshold = data ? TIER_THRESHOLDS[data.tier] : 0;
  const progressToNext = nextTier && data
    ? Math.min(100, Math.round(((data.points_earned_12m - currentTierThreshold) / (nextTierThreshold - currentTierThreshold)) * 100))
    : 100;
  const pointsToNextTier = nextTier && data ? Math.max(0, nextTierThreshold - data.points_earned_12m) : 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Loyalty Rewards</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isLoggedIn ? "Track your miles, tier progress, and rewards" : "Earn miles every time you fly"}
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => <Card key={i} className="p-5"><div className="h-16 bg-muted rounded" /></Card>)}
          </div>
        </div>
      )}

      {/* Logged-in dashboard */}
      {isLoggedIn && data && !loading && (
        <div className="mb-8 animate-fade-in space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Card className="p-5">
              <p className="text-xs font-medium text-muted-foreground mb-1">Points Balance</p>
              <p className="text-2xl font-bold text-blue-600">{data.points.toLocaleString()}</p>
              <p className="text-[10px] text-muted-foreground mt-1">Worth ${data.points_value.toFixed(2)}</p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium text-muted-foreground mb-1">Earned (12 months)</p>
              <p className="text-2xl font-bold">{data.points_earned_12m.toLocaleString()}</p>
              <p className="text-[10px] text-muted-foreground mt-1">Determines tier status</p>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium text-muted-foreground mb-1">Current Tier</p>
              <div className="flex items-center gap-2">
                <span className={`w-3 h-3 rounded-full ${TIER_COLORS[data.tier]}`} />
                <p className={`text-2xl font-bold capitalize ${TIER_TEXT_COLORS[data.tier]}`}>{data.tier}</p>
              </div>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-medium text-muted-foreground mb-1">
                {nextTier ? `To ${nextTier.charAt(0).toUpperCase() + nextTier.slice(1)}` : "Top Tier"}
              </p>
              <p className="text-2xl font-bold">
                {nextTier ? `${pointsToNextTier.toLocaleString()} pts` : "Achieved"}
              </p>
              <p className="text-[10px] text-muted-foreground mt-1">
                {nextTier ? "Earn in rolling 12 months" : "You have the highest tier"}
              </p>
            </Card>
          </div>

          {/* Progress Bar */}
          {nextTier && (
            <Card className="p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${TIER_COLORS[data.tier]}`} />
                  <span className="text-sm font-medium capitalize">{data.tier}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium capitalize">{nextTier}</span>
                  <span className={`w-2.5 h-2.5 rounded-full ${TIER_COLORS[nextTier]}`} />
                </div>
              </div>
              <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(progressToNext, 2)}%` }}
                />
              </div>
              <div className="flex justify-between mt-1.5">
                <span className="text-[10px] text-muted-foreground">{currentTierThreshold.toLocaleString()} pts</span>
                <span className="text-[10px] text-muted-foreground font-medium">{data.points_earned_12m.toLocaleString()} / {nextTierThreshold.toLocaleString()} pts</span>
              </div>
            </Card>
          )}

          {/* Points Actions */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link href="/">
              <Card className="p-5 hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer group h-full">
                <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/40 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </div>
                <h3 className="font-semibold text-sm">Book & Earn</h3>
                <p className="text-xs text-muted-foreground mt-1">Earn 10 pts per $1 on every booking</p>
              </Card>
            </Link>
            <Link href="/">
              <Card className="p-5 hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer group h-full">
                <div className="w-10 h-10 rounded-lg bg-green-50 dark:bg-green-900/40 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 className="font-semibold text-sm">Pay with Points</h3>
                <p className="text-xs text-muted-foreground mt-1">Use points at checkout ($0.01/pt)</p>
              </Card>
            </Link>
            <Card className="p-5 h-full">
              <div className="w-10 h-10 rounded-lg bg-purple-50 dark:bg-purple-900/40 flex items-center justify-center mb-3">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
                </svg>
              </div>
              <h3 className="font-semibold text-sm">Redeem Rewards</h3>
              <p className="text-xs text-muted-foreground mt-1">Lounge access, upgrades, extra bags</p>
            </Card>
          </div>

          {/* Transaction History */}
          {transactions.length > 0 && (
            <Card className="p-5">
              <h3 className="font-semibold text-sm mb-4">Recent Activity</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {transactions.slice(0, 15).map((txn) => (
                  <div key={txn.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                    <div className="flex items-center gap-3">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center ${txn.points > 0 ? "bg-green-100 dark:bg-green-900/30" : "bg-red-100 dark:bg-red-900/30"}`}>
                        {txn.points > 0 ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m0-16l-4 4m4-4l4 4" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 20V4m0 16l-4-4m4 4l4-4" />
                          </svg>
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{txn.source}</p>
                        <p className="text-[10px] text-muted-foreground capitalize">{txn.transaction_type} &middot; {new Date(txn.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</p>
                      </div>
                    </div>
                    <span className={`text-sm font-semibold ${txn.points > 0 ? "text-green-600" : "text-red-600"}`}>
                      {txn.points > 0 ? "+" : ""}{txn.points.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Not logged in */}
      {!isLoggedIn && !loading && (
        <Card className="p-6 mb-8 text-center">
          <p className="text-sm text-muted-foreground mb-3">Sign in to view your points balance and tier status</p>
          <Link href="/login">
            <Button size="sm">Sign In</Button>
          </Link>
        </Card>
      )}

      {/* Tier Benefits Table */}
      <h2 className="font-semibold text-lg mb-4">Tier Benefits</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {TIER_BENEFITS.map((t) => {
          const isCurrentTier = data?.tier === t.tier;
          return (
            <Card key={t.tier} className={`p-5 relative ${isCurrentTier ? "border-2 border-blue-500 shadow-md" : ""}`}>
              {isCurrentTier && (
                <Badge className="absolute -top-2 right-3 bg-blue-600 text-white text-[9px]">Your Tier</Badge>
              )}
              <div className="flex items-center gap-2 mb-3">
                <span className={`w-3 h-3 rounded-full ${TIER_COLORS[t.tier]}`} />
                <h3 className="font-semibold text-sm capitalize">{t.tier}</h3>
              </div>
              <p className="text-[10px] text-muted-foreground mb-3">
                {TIER_THRESHOLDS[t.tier] === 0 ? "0 - 24,999 pts/year" :
                  t.tier === "platinum" ? "100,000+ pts/year" :
                    `${TIER_THRESHOLDS[t.tier].toLocaleString()} - ${(TIER_THRESHOLDS[TIER_ORDER[TIER_ORDER.indexOf(t.tier) + 1]] - 1).toLocaleString()} pts/year`}
              </p>
              <ul className="space-y-1.5">
                {t.benefits.map((b, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    {b}
                  </li>
                ))}
              </ul>
            </Card>
          );
        })}
      </div>

      {/* How it works */}
      <h2 className="font-semibold text-lg mb-4">How Points Work</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Card className="p-5">
          <div className="w-9 h-9 rounded-lg bg-blue-50 dark:bg-blue-900/40 flex items-center justify-center mb-3">
            <span className="text-lg font-bold text-blue-600">1</span>
          </div>
          <h3 className="font-semibold text-sm mb-1">Earn</h3>
          <p className="text-xs text-muted-foreground">10 points per $1 spent on card payments. Points earned in the last 12 months determine your tier.</p>
        </Card>
        <Card className="p-5">
          <div className="w-9 h-9 rounded-lg bg-green-50 dark:bg-green-900/40 flex items-center justify-center mb-3">
            <span className="text-lg font-bold text-green-600">2</span>
          </div>
          <h3 className="font-semibold text-sm mb-1">Accumulate</h3>
          <p className="text-xs text-muted-foreground">Points never expire. Your tier is based on a rolling 12-month earning window.</p>
        </Card>
        <Card className="p-5">
          <div className="w-9 h-9 rounded-lg bg-amber-50 dark:bg-amber-900/40 flex items-center justify-center mb-3">
            <span className="text-lg font-bold text-amber-600">3</span>
          </div>
          <h3 className="font-semibold text-sm mb-1">Redeem</h3>
          <p className="text-xs text-muted-foreground">Use points at checkout: 100 pts = $1.00. Pay fully or partially with points on any booking.</p>
        </Card>
      </div>

      {/* Baggage Allowance by Tier */}
      <h2 className="font-semibold text-lg mb-4">Baggage Allowance by Tier</h2>
      <Card className="p-5 mb-8 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 text-xs font-medium text-muted-foreground">Cabin / Tier</th>
              <th className="text-center py-2 text-xs font-medium text-muted-foreground">Bronze</th>
              <th className="text-center py-2 text-xs font-medium text-muted-foreground">Silver</th>
              <th className="text-center py-2 text-xs font-medium text-muted-foreground">Gold</th>
              <th className="text-center py-2 text-xs font-medium text-muted-foreground">Platinum</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border/50">
              <td className="py-2.5 font-medium">Economy</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">1 bag (23kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">1 bag (28kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (28kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (33kg)</td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2.5 font-medium">Premium Economy</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (23kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (28kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">3 bags (28kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">3 bags (33kg)</td>
            </tr>
            <tr>
              <td className="py-2.5 font-medium">Business</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (32kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">2 bags (37kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">3 bags (37kg)</td>
              <td className="py-2.5 text-center text-xs text-muted-foreground">3 bags (42kg)</td>
            </tr>
          </tbody>
        </table>
      </Card>
    </div>
  );
}
