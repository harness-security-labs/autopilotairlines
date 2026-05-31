"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PaymentMethod {
  id: string;
  label: string;
  card_last_four: string;
  card_brand: string;
  expiry_month: number;
  expiry_year: number;
  is_default: boolean;
}

const BRAND_LOGOS: Record<string, string> = {
  visa: "/cards/visa.svg",
  mastercard: "/cards/mastercard.svg",
  amex: "/cards/amex.svg",
  discover: "/cards/discover.svg",
  rupay: "/cards/rupay.svg",
};


function detectCardBrand(number: string): string {
  const num = number.replace(/\s/g, "");
  if (num.startsWith("37")) return "amex";
  if (/^(60|65|81|82)/.test(num)) return "rupay";
  if (num.startsWith("4")) return "visa";
  if (num.startsWith("5")) return "mastercard";
  if (num.startsWith("6")) return "discover";
  return "unknown";
}

function formatCardNumber(value: string): string {
  const digits = value.replace(/\D/g, "");
  const brand = detectCardBrand(digits);
  if (brand === "amex") {
    const parts = [digits.slice(0, 4), digits.slice(4, 10), digits.slice(10, 15)];
    return parts.filter(Boolean).join(" ");
  }
  const parts = [digits.slice(0, 4), digits.slice(4, 8), digits.slice(8, 12), digits.slice(12, 16)];
  return parts.filter(Boolean).join(" ");
}

export default function PaymentsPage() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [cardNumber, setCardNumber] = useState("");
  const [expiryMonth, setExpiryMonth] = useState("01");
  const [expiryYear, setExpiryYear] = useState("2027");
  const [cvv, setCvv] = useState("");
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchMethods = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    setIsLoggedIn(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/payment-methods`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMethods(data);
      }
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchMethods();
  }, [fetchMethods]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${API_URL}/api/v1/payment-methods`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          card_number: cardNumber.replace(/\s/g, ""),
          cvv,
          expiry_month: parseInt(expiryMonth),
          expiry_year: parseInt(expiryYear),
          label: label || undefined,
        }),
      });
      if (res.ok) {
        setCardNumber("");
        setCvv("");
        setExpiryMonth("01");
        setExpiryYear("2027");
        setLabel("");
        setShowForm(false);
        await fetchMethods();
      }
    } catch {}
    setSubmitting(false);
  };

  const handleDelete = async (id: string) => {
    const token = localStorage.getItem("token");
    await fetch(`${API_URL}/api/v1/payment-methods/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    await fetchMethods();
  };

  const handleSetDefault = async (id: string) => {
    const token = localStorage.getItem("token");
    await fetch(`${API_URL}/api/v1/payment-methods/${id}/default`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    await fetchMethods();
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-48" />
          <div className="h-24 bg-muted rounded" />
          <div className="h-24 bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10 text-center">
        <h1 className="text-2xl font-bold mb-2">Payment Methods</h1>
        <p className="text-muted-foreground mb-4">Sign in to manage your saved payment methods.</p>
        <Link href="/login">
          <Button>Sign In</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Payment Methods</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your saved cards for bookings and payments</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "Add Card"}
        </Button>
      </div>

      {showForm && (
        <Card className="p-5 mb-6">
          <form onSubmit={handleAdd} className="space-y-4">
            <div>
              <label className="text-sm font-medium block mb-1.5">Card Number</label>
              <div className="relative">
                <input
                  type="text"
                  value={cardNumber}
                  onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                  placeholder="4242 4242 4242 4242"
                  required
                  maxLength={19}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 pr-20 text-sm font-mono outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                />
                {cardNumber.replace(/\s/g, "").length > 0 && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2">
                    {BRAND_LOGOS[detectCardBrand(cardNumber)] ? (
                      <img src={BRAND_LOGOS[detectCardBrand(cardNumber)]} alt={detectCardBrand(cardNumber)} className="h-5 w-auto" />
                    ) : (
                      <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">Card</span>
                    )}
                  </span>
                )}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">CVV</label>
              <input
                type="text"
                value={cvv}
                onChange={(e) => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
                placeholder="123"
                required
                maxLength={4}
                className="w-32 rounded-md border border-border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-sm font-medium block mb-1.5">Month</label>
                <select
                  value={expiryMonth}
                  onChange={(e) => setExpiryMonth(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                >
                  {Array.from({ length: 12 }, (_, i) => (
                    <option key={i + 1} value={String(i + 1).padStart(2, "0")}>
                      {String(i + 1).padStart(2, "0")}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">Year</label>
                <select
                  value={expiryYear}
                  onChange={(e) => setExpiryYear(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                >
                  {Array.from({ length: 10 }, (_, i) => (
                    <option key={2025 + i} value={String(2025 + i)}>
                      {2025 + i}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">Label (optional)</label>
                <input
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="My Visa"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                />
              </div>
            </div>
            <Button type="submit" disabled={submitting || !cardNumber.trim()}>
              {submitting ? "Saving..." : "Save Card"}
            </Button>
          </form>
        </Card>
      )}

      {methods.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground">No saved payment methods yet.</p>
          <p className="text-sm text-muted-foreground mt-1">Add a card to use for bookings and payments.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {methods.map((m) => (
            <Card key={m.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-7 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden">
                    {BRAND_LOGOS[m.card_brand] ? (
                      <img src={BRAND_LOGOS[m.card_brand]} alt={m.card_brand} className="h-5 w-auto object-contain" />
                    ) : (
                      <span className="text-[10px] font-bold uppercase text-muted-foreground">Card</span>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium">{m.label}</p>
                      {m.is_default && (
                        <Badge variant="secondary" className="text-[10px]">Default</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground font-mono">
                      ••••{m.card_last_four} &middot; Expires {String(m.expiry_month).padStart(2, "0")}/{m.expiry_year}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!m.is_default && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSetDefault(m.id)}
                    >
                      Set Default
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(m.id)}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
