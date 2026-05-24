"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BoardingPass {
  booking_id: string;
  pnr: string;
  passenger_name: string;
  seat: string;
  gate: string;
  boarding_group: string;
  boarding_pass_url: string;
  flight_number?: string;
  origin?: string;
  destination?: string;
  departure?: string;
  arrival?: string;
  boarding_time?: string;
  travel_date?: string;
  aircraft?: string;
}

export default function CheckInPage() {
  return (
    <Suspense fallback={<div className="max-w-3xl mx-auto px-4 py-8"><Card className="p-6"><div className="h-32 bg-muted rounded animate-pulse" /></Card></div>}>
      <CheckInContent />
    </Suspense>
  );
}

const BASE_BAGGAGE: Record<string, { checkedCount: number; checkedKg: number; carryonCount: number; carryonKg: number }> = {
  economy: { checkedCount: 1, checkedKg: 23, carryonCount: 1, carryonKg: 7 },
  premium_economy: { checkedCount: 2, checkedKg: 23, carryonCount: 1, carryonKg: 10 },
  business: { checkedCount: 2, checkedKg: 32, carryonCount: 2, carryonKg: 10 },
};

const TIER_BONUS: Record<string, { extraBags: number; extraKg: number }> = {
  bronze: { extraBags: 0, extraKg: 0 },
  silver: { extraBags: 0, extraKg: 5 },
  gold: { extraBags: 1, extraKg: 5 },
  platinum: { extraBags: 1, extraKg: 10 },
};

function getBaggageAllowance(cabin: string, tier: string) {
  const base = BASE_BAGGAGE[cabin] || BASE_BAGGAGE.economy;
  const bonus = TIER_BONUS[tier] || TIER_BONUS.bronze;
  const checkedCount = base.checkedCount + bonus.extraBags;
  const checkedKg = base.checkedKg + bonus.extraKg;
  const carryonKg = base.carryonKg + (bonus.extraKg > 0 ? 3 : 0);
  return {
    checked: `${checkedCount} checked bag${checkedCount > 1 ? "s" : ""} (${checkedKg}kg${checkedCount > 1 ? " each" : ""})`,
    carryon: `${base.carryonCount} carry-on${base.carryonCount > 1 ? "s" : ""} (${carryonKg}kg${base.carryonCount > 1 ? " each" : ""})`,
    maxCheckedBags: checkedCount + 1,
  };
}

function CheckInContent() {
  const searchParams = useSearchParams();

  const [pnr, setPnr] = useState("");
  const [lastName, setLastName] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [bookingId, setBookingId] = useState<string | null>(null);
  const [bookingStatus, setBookingStatus] = useState("");
  const [passengerName, setPassengerName] = useState("");
  const [cabinClass, setCabinClass] = useState("economy");
  const [loyaltyTier, setLoyaltyTier] = useState("bronze");

  const [seatPref, setSeatPref] = useState("window");
  const [checkedBags, setCheckedBags] = useState(1);
  const [confirmBagContents, setConfirmBagContents] = useState(false);
  const [confirmNoDangerous, setConfirmNoDangerous] = useState(false);
  const [confirmBagAllowance, setConfirmBagAllowance] = useState(false);
  const [checkinLoading, setCheckinLoading] = useState(false);
  const [undoLoading, setUndoLoading] = useState(false);
  const [boardingPass, setBoardingPass] = useState<BoardingPass | null>(null);
  const boardingPassRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const urlPnr = searchParams.get("pnr");
    if (urlPnr) {
      setPnr(urlPnr.toUpperCase());
      lookupByPnr(urlPnr.toUpperCase());
    }
  }, [searchParams]);

  const lookupByPnr = async (pnrValue: string) => {
    setLookupLoading(true);
    setLookupError("");
    setBookingId(null);
    setBoardingPass(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/bookings/lookup?pnr=${encodeURIComponent(pnrValue)}&last_name=`);
      if (res.ok) {
        const data = await res.json();
        setBookingId(data.id);
        setBookingStatus(data.status);
        setPassengerName(data.passenger_name);
        setCabinClass(data.cabin_class || "economy");
        if (data.status === "checked_in") {
          await fetchBoardingPass(data.id);
        }
        const token = localStorage.getItem("token");
        if (token) {
          fetch(`${API_URL}/api/v1/loyalty/balance`, {
            headers: { Authorization: `Bearer ${token}` },
          })
            .then((r) => r.ok ? r.json() : null)
            .then((d) => { if (d) setLoyaltyTier(d.tier || "bronze"); })
            .catch(() => {});
        }
      } else {
        setLookupError("Booking not found. Check your PNR and try again.");
      }
    } catch {
      setLookupError("Error looking up booking.");
    }
    setLookupLoading(false);
  };

  const lookupBooking = async () => {
    if (!pnr.trim()) return;
    await lookupByPnr(pnr.trim().toUpperCase());
  };

  const fetchBoardingPass = async (bId: string) => {
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/api/v1/checkin`, {
        method: "POST",
        headers,
        body: JSON.stringify({ booking_id: bId, seat_preference: "window" }),
      });
      if (res.ok) {
        setBoardingPass(await res.json());
      }
    } catch {}
  };

  const doCheckin = async () => {
    if (!bookingId) return;
    setCheckinLoading(true);
    setLookupError("");
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${API_URL}/api/v1/checkin`, {
        method: "POST",
        headers,
        body: JSON.stringify({ booking_id: bookingId, seat_preference: seatPref }),
      });
      if (res.ok) {
        const data = await res.json();
        setBoardingPass(data);
        setBookingStatus("checked_in");
      } else {
        setLookupError("Check-in failed. Please try again.");
      }
    } catch {
      setLookupError("Error during check-in.");
    }
    setCheckinLoading(false);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Online Check-in</h1>
        <p className="text-sm text-muted-foreground mt-1">Check in up to 24 hours before departure</p>
      </div>

      {/* Boarding Pass - shown after check-in */}
      {boardingPass && (
        <div className="mb-6 animate-fade-in" ref={boardingPassRef}>
          <Card className="overflow-hidden border-2 border-blue-200 dark:border-blue-800">
            <div className="bg-blue-600 dark:bg-blue-800 px-6 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                </svg>
                <span className="text-white font-bold text-sm tracking-wide">AUTOPILOT AIRLINES</span>
              </div>
              <Badge className="bg-green-500 text-white border-0">BOARDING PASS</Badge>
            </div>

            <div className="p-6 bg-gradient-to-br from-blue-50 to-white dark:from-blue-950 dark:to-slate-900">
              <div className="flex flex-col sm:flex-row gap-6">
                <div className="flex-1 space-y-4">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Passenger</p>
                    <p className="font-bold text-lg">{boardingPass.passenger_name}</p>
                  </div>

                  {boardingPass.flight_number && (
                    <div className="p-3 rounded-lg bg-white/60 dark:bg-slate-800/40 border border-border/30">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono font-bold text-sm">{boardingPass.flight_number}</span>
                        {boardingPass.aircraft && <span className="text-[10px] text-muted-foreground">{boardingPass.aircraft}</span>}
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-center">
                          <p className="text-xl font-bold">{boardingPass.origin}</p>
                          {boardingPass.departure && (
                            <p className="text-xs text-muted-foreground">{new Date(boardingPass.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                          )}
                        </div>
                        <div className="flex-1 flex flex-col items-center">
                          <div className="w-full flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full border-2 border-blue-600" />
                            <div className="flex-1 border-t-2 border-dashed border-blue-300" />
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
                              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                            </svg>
                            <div className="flex-1 border-t-2 border-dashed border-blue-300" />
                            <div className="w-2 h-2 rounded-full bg-blue-600" />
                          </div>
                          {boardingPass.travel_date && (
                            <p className="text-[10px] text-muted-foreground mt-1">{new Date(boardingPass.travel_date + "T00:00:00").toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</p>
                          )}
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold">{boardingPass.destination}</p>
                          {boardingPass.arrival && (
                            <p className="text-xs text-muted-foreground">{new Date(boardingPass.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-4 gap-3">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">PNR</p>
                      <p className="font-mono font-bold text-sm">{boardingPass.pnr}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">Seat</p>
                      <p className="font-bold text-2xl text-blue-600">{boardingPass.seat}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">Gate</p>
                      <p className="font-bold text-2xl">{boardingPass.gate}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">Boarding</p>
                      <p className="font-bold text-lg">
                        {boardingPass.boarding_time
                          ? new Date(boardingPass.boarding_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                          : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border/50">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">Boarding Group</p>
                      <p className="font-semibold text-base">{boardingPass.boarding_group}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">Status</p>
                      <p className="font-semibold text-green-600">Confirmed</p>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col items-center justify-center sm:border-l sm:border-dashed sm:border-border/60 sm:pl-6">
                  <div className="bg-white p-3 rounded-lg shadow-sm">
                    <QRCodeSVG
                      value={boardingPass.boarding_pass_url}
                      size={140}
                      level="M"
                      includeMargin={false}
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-2 font-mono">{boardingPass.pnr}</p>
                </div>
              </div>
            </div>

            <div className="px-6 py-3 bg-muted/30 border-t border-border/50 flex justify-between items-center">
              <p className="text-xs text-muted-foreground">Scan QR code at the gate for boarding</p>
              <div className="flex gap-2">
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={undoLoading}
                  onClick={async () => {
                    if (!confirm("Are you sure you want to undo check-in? You will need to check in again.")) return;
                    setUndoLoading(true);
                    try {
                      const token = localStorage.getItem("token");
                      const headers: Record<string, string> = { "Content-Type": "application/json" };
                      if (token) headers["Authorization"] = `Bearer ${token}`;
                      const res = await fetch(`${API_URL}/api/v1/checkin/undo`, {
                        method: "POST",
                        headers,
                        body: JSON.stringify({ booking_id: boardingPass.booking_id }),
                      });
                      if (res.ok) {
                        setBoardingPass(null);
                        setBookingStatus("confirmed");
                        setConfirmBagContents(false);
                        setConfirmNoDangerous(false);
                        setConfirmBagAllowance(false);
                      } else {
                        alert("Failed to undo check-in.");
                      }
                    } catch {
                      alert("Error undoing check-in.");
                    }
                    setUndoLoading(false);
                  }}
                >
                  {undoLoading ? "..." : "Undo Check-in"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (!boardingPassRef.current) return;
                    const printWindow = window.open("", "_blank");
                    if (!printWindow) return;
                    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
                      .map((el) => el.outerHTML)
                      .join("\n");
                    const content = boardingPassRef.current.innerHTML;
                    printWindow.document.write(`<!DOCTYPE html><html><head><title>Boarding Pass - ${boardingPass.pnr}</title>${styles}<style>
                      body { padding: 40px; background: white; }
                      @media print { body { padding: 10px; } button { display: none !important; } }
                      button { display: none !important; }
                    </style></head><body><div class="max-w-2xl mx-auto">${content}</div></body></html>`);
                    printWindow.document.close();
                    setTimeout(() => { printWindow.print(); }, 600);
                  }}
                >
                  Download Pass
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Lookup Form */}
      {!boardingPass && !bookingId && (
        <Card className="p-6 mb-6">
          <h2 className="font-semibold mb-4">Find Your Booking</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Booking Reference (PNR)</label>
              <Input value={pnr} onChange={(e) => setPnr(e.target.value.toUpperCase())} placeholder="ABC123" className="uppercase" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Last Name</label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Smith" />
            </div>
            <div className="flex items-end">
              <Button onClick={lookupBooking} disabled={lookupLoading || !pnr.trim()} className="w-full">
                {lookupLoading ? "Searching..." : "Find Booking"}
              </Button>
            </div>
          </div>
          {lookupError && <p className="mt-3 text-sm text-destructive">{lookupError}</p>}
        </Card>
      )}

      {/* Loading state when auto-looking up from URL */}
      {lookupLoading && !bookingId && !boardingPass && (
        <Card className="p-6 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-muted-foreground">Looking up booking {pnr}...</p>
          </div>
        </Card>
      )}

      {/* Booking Found - Seat Selection */}
      {bookingId && !boardingPass && (
        <Card className="p-6 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold">Ready to Check In</h2>
              <p className="text-sm text-muted-foreground">{passengerName} &middot; PNR: {pnr.toUpperCase()}</p>
            </div>
            <Badge variant={bookingStatus === "confirmed" ? "default" : "secondary"}>{bookingStatus.replace("_", " ")}</Badge>
          </div>

          {bookingStatus === "checked_in" ? (
            <div>
              <p className="text-sm text-muted-foreground mb-3">This booking is already checked in. Retrieving your boarding pass...</p>
              <Button onClick={() => fetchBoardingPass(bookingId)} variant="outline">
                Load Boarding Pass
              </Button>
            </div>
          ) : bookingStatus !== "confirmed" ? (
            <p className="text-sm text-destructive">Only confirmed bookings can be checked in.</p>
          ) : (
            <div className="space-y-5">
              {/* Cabin Class & Baggage Info */}
              <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Cabin Class</span>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="capitalize text-[10px]">{loyaltyTier} tier</Badge>
                    <Badge variant="default" className="capitalize">{cabinClass.replace("_", " ")}</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Checked Baggage</p>
                    <p className="font-medium">{getBaggageAllowance(cabinClass, loyaltyTier).checked}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Carry-on</p>
                    <p className="font-medium">{getBaggageAllowance(cabinClass, loyaltyTier).carryon}</p>
                  </div>
                </div>
                {TIER_BONUS[loyaltyTier]?.extraBags > 0 || TIER_BONUS[loyaltyTier]?.extraKg > 0 ? (
                  <p className="text-[10px] text-blue-600 mt-2">
                    Tier bonus: {TIER_BONUS[loyaltyTier].extraBags > 0 ? `+${TIER_BONUS[loyaltyTier].extraBags} bag` : ""}
                    {TIER_BONUS[loyaltyTier].extraBags > 0 && TIER_BONUS[loyaltyTier].extraKg > 0 ? ", " : ""}
                    {TIER_BONUS[loyaltyTier].extraKg > 0 ? `+${TIER_BONUS[loyaltyTier].extraKg}kg per bag` : ""}
                  </p>
                ) : null}
              </div>

              {/* Seat Preference */}
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-2 block">Seat Preference</label>
                <div className="flex gap-2">
                  {["window", "middle", "aisle"].map((pref) => (
                    <button
                      key={pref}
                      onClick={() => setSeatPref(pref)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                        seatPref === pref
                          ? "bg-blue-600 text-white"
                          : "bg-muted text-muted-foreground hover:bg-muted/80"
                      }`}
                    >
                      {pref}
                    </button>
                  ))}
                </div>
              </div>

              {/* Checked Bags Count */}
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-2 block">Number of Checked Bags</label>
                <select
                  value={checkedBags}
                  onChange={(e) => setCheckedBags(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                >
                  {Array.from({ length: getBaggageAllowance(cabinClass, loyaltyTier).maxCheckedBags + 1 }, (_, i) => (
                    <option key={i} value={i}>
                      {i} bag{i !== 1 ? "s" : ""}{i > getBaggageAllowance(cabinClass, loyaltyTier).maxCheckedBags - 1 ? " (extra fee applies)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              {/* Confirmation Checkboxes */}
              <div className="space-y-3 p-4 rounded-lg border border-border bg-muted/30">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pre-flight Confirmation</p>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={confirmBagContents}
                    onChange={(e) => setConfirmBagContents(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded border-border"
                  />
                  <span className="text-sm">I confirm I am aware of the contents of all my baggage and have packed them myself</span>
                </label>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={confirmNoDangerous}
                    onChange={(e) => setConfirmNoDangerous(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded border-border"
                  />
                  <span className="text-sm">I confirm I am not carrying any prohibited or dangerous items (explosives, flammable materials, sharp objects, lithium batteries exceeding limits)</span>
                </label>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={confirmBagAllowance}
                    onChange={(e) => setConfirmBagAllowance(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded border-border"
                  />
                  <span className="text-sm">I acknowledge my baggage allowance for <strong className="capitalize">{cabinClass.replace("_", " ")}</strong> class ({loyaltyTier} tier): {getBaggageAllowance(cabinClass, loyaltyTier).checked}, {getBaggageAllowance(cabinClass, loyaltyTier).carryon}</span>
                </label>
              </div>

              <Button
                onClick={doCheckin}
                disabled={checkinLoading || !confirmBagContents || !confirmNoDangerous || !confirmBagAllowance}
                className="w-full"
              >
                {checkinLoading ? "Checking in..." : "Complete Check-in"}
              </Button>
              {(!confirmBagContents || !confirmNoDangerous || !confirmBagAllowance) && (
                <p className="text-xs text-muted-foreground text-center">Please confirm all items above to proceed</p>
              )}
            </div>
          )}
          {lookupError && <p className="mt-3 text-sm text-destructive">{lookupError}</p>}
        </Card>
      )}
    </div>
  );
}
