"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Booking {
  id: string;
  flight_id: string;
  status: string;
  pnr: string;
  passenger_name: string;
  passenger_email: string;
  created_at: string;
}

export default function BookingsPage() {
  const [pnr, setPnr] = useState("");
  const [lastName, setLastName] = useState("");
  const [lookupResult, setLookupResult] = useState<Booking | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);

  const [bookings, setBookings] = useState<Booking[]>([]);
  const [bookingsLoading, setBookingsLoading] = useState(true);
  const [showMyBookings, setShowMyBookings] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setBookingsLoading(false);
      return;
    }
    setIsLoggedIn(true);
    fetch(`${API_URL}/api/v1/bookings`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        setBookings(data);
        setBookingsLoading(false);
      })
      .catch(() => setBookingsLoading(false));
  }, []);

  const lookupBooking = async () => {
    if (!pnr.trim()) return;
    setLookupLoading(true);
    setLookupError("");
    setLookupResult(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/bookings/lookup?pnr=${encodeURIComponent(pnr.trim().toUpperCase())}&last_name=${encodeURIComponent(lastName.trim())}`);
      if (res.ok) {
        setLookupResult(await res.json());
      } else {
        setLookupError("Booking not found. Please check your reference and try again.");
      }
    } catch {
      setLookupError("Unable to look up booking. Please try again.");
    }
    setLookupLoading(false);
  };

  const cancelBooking = async (bookingId: string) => {
    if (!confirm("Are you sure you want to cancel this booking?")) return;
    const token = localStorage.getItem("token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    try {
      const res = await fetch(`${API_URL}/api/v1/bookings/${bookingId}/cancel`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        setBookings((prev) => prev.map((b) => b.id === bookingId ? { ...b, status: "cancelled" } : b));
        if (lookupResult?.id === bookingId) {
          setLookupResult({ ...lookupResult, status: "cancelled" });
        }
      }
    } catch {}
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Manage Booking</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Retrieve your booking using your confirmation code
        </p>
      </div>

      {/* PNR Lookup */}
      <Card className="p-6 mb-8">
        <h2 className="font-semibold mb-4">Retrieve Booking</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Booking Reference (PNR)</label>
            <Input
              placeholder="e.g. ABC123"
              value={pnr}
              onChange={(e) => setPnr(e.target.value.toUpperCase())}
              className="uppercase"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Last Name</label>
            <Input
              placeholder="Passenger last name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button onClick={lookupBooking} disabled={lookupLoading || !pnr.trim()} className="w-full">
              {lookupLoading ? "Searching..." : "Find Booking"}
            </Button>
          </div>
        </div>

        {lookupError && (
          <p className="mt-4 text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">{lookupError}</p>
        )}

        {lookupResult && (
          <div className="mt-4 p-4 rounded-lg border border-border bg-muted/30">
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-semibold">PNR: {lookupResult.pnr}</p>
                  <Badge variant={lookupResult.status === "confirmed" ? "default" : lookupResult.status === "cancelled" ? "destructive" : "secondary"}>
                    {lookupResult.status}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{lookupResult.passenger_name}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Booked {new Date(lookupResult.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Link href={`/bookings/${lookupResult.id}`}>
                  <Button variant="outline" size="sm">Details</Button>
                </Link>
                {lookupResult.status === "confirmed" && (
                  <Button variant="outline" size="sm" onClick={() => cancelBooking(lookupResult.id)}>Cancel</Button>
                )}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* My Bookings */}
      {isLoggedIn && bookings.length > 0 && (
        <div>
          <button
            onClick={() => setShowMyBookings(!showMyBookings)}
            className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-3"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`w-4 h-4 transition-transform ${showMyBookings ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            My Bookings ({bookings.length})
          </button>

          {showMyBookings && (
            <div className="space-y-3 animate-fade-in">
              {bookings.map((booking) => (
                <Link key={booking.id} href={`/bookings/${booking.id}`}>
                  <Card className="p-4 hover:shadow-md transition-shadow cursor-pointer mb-3">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-semibold text-sm">PNR: {booking.pnr}</p>
                          <Badge variant={booking.status === "confirmed" ? "default" : booking.status === "cancelled" ? "destructive" : "secondary"}>
                            {booking.status}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{booking.passenger_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(booking.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {booking.status === "confirmed" && (
                        <Button variant="outline" size="sm" onClick={(e) => { e.preventDefault(); cancelBooking(booking.id); }}>
                          Cancel
                        </Button>
                      )}
                    </div>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
