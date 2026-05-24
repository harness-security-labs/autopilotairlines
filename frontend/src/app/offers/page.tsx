"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

interface Offer {
  code: string;
  discount_percent: number;
  description: string;
  type: string;
  valid_until?: string;
  min_passengers?: number;
  conditions?: OfferConditions;
}

export default function OffersPage() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/v1/bookings/coupons/available`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.offers) setOffers(data.offers);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(code);
    setTimeout(() => setCopied(""), 2000);
  };

  const conditionBadges = (c?: OfferConditions) => {
    if (!c || Object.keys(c).length === 0) return null;
    const badges: string[] = [];
    if (c.new_user) badges.push("New users only");
    if (c.loyalty_tier_min) badges.push(`${c.loyalty_tier_min}+ tier`);
    if (c.max_uses_total) badges.push(`First ${c.max_uses_total} uses`);
    if (c.max_uses_per_user) badges.push(`${c.max_uses_per_user} per user`);
    if (c.cabin_class) badges.push(c.cabin_class.join(", "));
    if (c.keywords) badges.push(c.keywords.join(", ") + " flights");
    if (c.min_booking_value) badges.push(`$${c.min_booking_value}+ booking`);
    if (c.min_bookings_last_n_days) badges.push(`${c.min_bookings_last_n_days.min_bookings}+ bookings in ${c.min_bookings_last_n_days.days}d`);
    if (c.routes) badges.push(c.routes.map(r => `${r.origin}-${r.destination}`).join(", "));
    if (badges.length === 0) return null;
    return (
      <div className="flex flex-wrap gap-1 mt-1.5">
        {badges.map((b) => (
          <span key={b} className="text-[9px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">{b}</span>
        ))}
      </div>
    );
  };

  const campaignOffers = offers.filter((o) => o.type === "campaign");
  const holidayOffers = offers.filter((o) => o.type === "holiday");
  const bulkOffers = offers.filter((o) => o.type === "bulk");
  const generalOffers = offers.filter((o) => o.type === "general");

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 bg-muted rounded" />
          <div className="h-48 bg-muted rounded-xl" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-32 bg-muted rounded" />
            <div className="h-32 bg-muted rounded" />
            <div className="h-32 bg-muted rounded" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-3.5rem)]">
      {/* Hero Banner */}
      {holidayOffers.length > 0 && (
        <div className="relative overflow-hidden bg-gradient-to-r from-orange-500 via-pink-500 to-purple-600 dark:from-orange-700 dark:via-pink-800 dark:to-purple-900">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-4 left-[5%] w-32 h-32 bg-white/10 rounded-full blur-2xl animate-float" />
            <div className="absolute bottom-4 right-[10%] w-24 h-24 bg-yellow-300/10 rounded-full blur-2xl animate-float" style={{ animationDelay: "1s" }} />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-white/5 rounded-full blur-3xl" />
          </div>

          <div className="relative max-w-5xl mx-auto px-4 py-12 sm:py-16 text-center">
            <Badge className="bg-white/20 text-white border-white/30 mb-4 text-xs">Limited Time</Badge>
            <h1 className="text-3xl sm:text-5xl font-bold text-white mb-3 tracking-tight animate-fade-in">
              {holidayOffers[0].description.split("—")[0].trim()}
            </h1>
            <p className="text-white/80 text-lg mb-6 animate-fade-in">
              Save up to <span className="font-bold text-yellow-200">{holidayOffers[0].discount_percent}%</span> on select routes
            </p>
            <div className="flex items-center justify-center gap-3 animate-slide-up">
              <div className="bg-white/20 backdrop-blur-sm border border-white/30 rounded-lg px-5 py-3 flex items-center gap-3">
                <span className="font-mono text-xl font-bold text-white tracking-wider">{holidayOffers[0].code}</span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => copyCode(holidayOffers[0].code)}
                  className="text-xs"
                >
                  {copied === holidayOffers[0].code ? "Copied!" : "Copy"}
                </Button>
              </div>
            </div>
            {holidayOffers[0].valid_until && (
              <p className="text-white/60 text-xs mt-4">
                Valid until {new Date(holidayOffers[0].valid_until).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Campaign Banner */}
      {campaignOffers.length > 0 && (
        <div className="relative overflow-hidden bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 dark:from-emerald-700 dark:via-teal-800 dark:to-cyan-900">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-2 right-[8%] w-28 h-28 bg-white/10 rounded-full blur-2xl" />
            <div className="absolute bottom-2 left-[5%] w-20 h-20 bg-yellow-200/10 rounded-full blur-2xl" />
          </div>
          <div className="relative max-w-5xl mx-auto px-4 py-8 sm:py-10">
            <div className="flex flex-col sm:flex-row items-center gap-6">
              <div className="shrink-0 w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
              </div>
              <div className="flex-1 text-center sm:text-left">
                <Badge className="bg-white/20 text-white border-white/30 mb-2 text-[10px]">Exclusive Deal</Badge>
                <h2 className="text-2xl sm:text-3xl font-bold text-white mb-1">{campaignOffers[0].description}</h2>
                <p className="text-white/70 text-sm">
                  Unlock <span className="font-bold text-yellow-200">{campaignOffers[0].discount_percent}% savings</span> with code <span className="font-mono font-bold text-white">{campaignOffers[0].code}</span> — book now before it expires
                </p>
                {campaignOffers[0].conditions && Object.keys(campaignOffers[0].conditions).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2 justify-center sm:justify-start">
                    {campaignOffers[0].conditions.loyalty_tier_min && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">{campaignOffers[0].conditions.loyalty_tier_min}+ tier</span>}
                    {campaignOffers[0].conditions.keywords && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">{campaignOffers[0].conditions.keywords.join(", ")} flights</span>}
                    {campaignOffers[0].conditions.cabin_class && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">{campaignOffers[0].conditions.cabin_class.join(", ")}</span>}
                    {campaignOffers[0].conditions.max_uses_total && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">First {campaignOffers[0].conditions.max_uses_total} uses</span>}
                    {campaignOffers[0].conditions.new_user && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">New users</span>}
                    {campaignOffers[0].conditions.min_booking_value && <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/20 text-white">${campaignOffers[0].conditions.min_booking_value}+ booking</span>}
                  </div>
                )}
              </div>
              <div className="shrink-0 flex flex-col items-center gap-2">
                <div className="bg-white/20 backdrop-blur-sm border border-white/30 rounded-lg px-5 py-3">
                  <span className="font-mono text-xl font-bold text-white tracking-wider">{campaignOffers[0].code}</span>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => copyCode(campaignOffers[0].code)}
                  className="text-xs"
                >
                  {copied === campaignOffers[0].code ? "Copied!" : "Copy Code"}
                </Button>
              </div>
            </div>
            {campaignOffers.length > 1 && (
              <div className="mt-6 pt-4 border-t border-white/20 flex flex-wrap gap-3 justify-center sm:justify-start">
                {campaignOffers.slice(1).map((offer) => (
                  <div key={offer.code} className="flex items-center gap-2 bg-white/10 backdrop-blur-sm rounded-full px-4 py-2">
                    <span className="font-mono text-sm font-bold text-white">{offer.code}</span>
                    <span className="text-white/70 text-xs">{offer.discount_percent}% off</span>
                    <button onClick={() => copyCode(offer.code)} className="text-[10px] text-yellow-200 hover:underline ml-1">
                      {copied === offer.code ? "Copied!" : "Copy"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 py-10">
        {/* Holiday Offers */}
        {holidayOffers.length > 0 && (
          <section className="mb-10">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-8 h-8 rounded-lg bg-orange-100 dark:bg-orange-900/40 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold">Holiday Specials</h2>
              <Badge variant="destructive" className="text-[10px]">Active Now</Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {holidayOffers.map((offer) => (
                <Card key={offer.code} className="p-5 relative overflow-hidden group hover:shadow-lg transition-all duration-200 border-orange-200/50 dark:border-orange-800/30">
                  <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-orange-100 to-transparent dark:from-orange-900/20 rounded-bl-3xl" />
                  <div className="flex items-start gap-4">
                    <div className="shrink-0 w-14 h-14 rounded-xl bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center shadow-lg shadow-orange-200/50 dark:shadow-none">
                      <span className="text-white font-bold text-lg">{offer.discount_percent}%</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm mb-1">{offer.description}</p>
                      <div className="flex items-center gap-2">
                        <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">{offer.code}</code>
                        <button
                          onClick={() => copyCode(offer.code)}
                          className="text-[10px] text-blue-600 hover:underline"
                        >
                          {copied === offer.code ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      {offer.valid_until && (
                        <p className="text-[10px] text-muted-foreground mt-1.5">
                          Expires {new Date(offer.valid_until).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Bulk Booking Discounts */}
        <section className="mb-10">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold">Group & Bulk Discounts</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {bulkOffers.map((offer, i) => (
              <Card key={offer.code} className={`p-5 relative overflow-hidden hover:shadow-lg transition-all duration-200 ${i === 2 ? "border-blue-300 dark:border-blue-700 ring-1 ring-blue-200 dark:ring-blue-800" : ""}`}>
                {i === 2 && (
                  <Badge className="absolute top-3 right-3 text-[9px] bg-blue-600">Best Value</Badge>
                )}
                <div className="text-center">
                  <div className={`w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-3 ${
                    i === 0 ? "bg-blue-100 dark:bg-blue-900/40" : i === 1 ? "bg-indigo-100 dark:bg-indigo-900/40" : "bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-200/50 dark:shadow-none"
                  }`}>
                    <span className={`font-bold text-2xl ${i === 2 ? "text-white" : i === 0 ? "text-blue-600" : "text-indigo-600"}`}>
                      {offer.discount_percent}%
                    </span>
                  </div>
                  <p className="font-semibold text-sm mb-1">{offer.min_passengers}+ Passengers</p>
                  <p className="text-xs text-muted-foreground mb-3">{offer.description}</p>
                  <div className="flex items-center justify-center gap-2">
                    <code className="text-xs bg-muted px-2 py-1 rounded font-mono">{offer.code}</code>
                    <button
                      onClick={() => copyCode(offer.code)}
                      className="text-[10px] text-blue-600 hover:underline"
                    >
                      {copied === offer.code ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>

        {/* General Offers */}
        <section className="mb-10">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-8 h-8 rounded-lg bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold">Everyday Offers</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {generalOffers.map((offer) => (
              <Card key={offer.code} className="p-4 flex items-center justify-between hover:shadow-md transition-all duration-200">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/40 flex items-center justify-center shrink-0">
                    <span className="text-sm font-bold text-green-600">{offer.discount_percent}%</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium">{offer.description}</p>
                    <code className="text-[10px] text-muted-foreground font-mono">{offer.code}</code>
                    {conditionBadges(offer.conditions)}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyCode(offer.code)}
                  className="text-xs"
                >
                  {copied === offer.code ? "Copied!" : "Copy Code"}
                </Button>
              </Card>
            ))}
          </div>
        </section>

        {/* CTA */}
        <Card className="p-8 text-center bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border-blue-200/50 dark:border-blue-800/30">
          <h3 className="text-lg font-semibold mb-2">Ready to Book?</h3>
          <p className="text-sm text-muted-foreground mb-5">Apply any of these codes during checkout to save on your next flight.</p>
          <Link href="/">
            <Button size="lg">Search Flights</Button>
          </Link>
        </Card>
      </div>
    </div>
  );
}
