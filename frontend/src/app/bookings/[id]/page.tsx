"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Booking {
  id: string;
  flight_id: string;
  user_id: string;
  status: string;
  pnr: string;
  passenger_name: string;
  passenger_email: string;
  cabin_class?: string;
  created_at: string;
}

interface Receipt {
  booking: {
    id: string;
    pnr: string;
    status: string;
    passenger_name: string;
    passenger_email: string;
    cabin_class: string;
    travel_date: string | null;
    coupon_code: string | null;
    created_at: string;
  };
  flight: {
    id: string | null;
    flight_number: string | null;
    origin: string | null;
    destination: string | null;
    departure: string | null;
    arrival: string | null;
    aircraft: string | null;
  };
  pricing: {
    base_fare: number;
    taxes: number;
    subtotal: number;
    coupon_code: string | null;
    coupon_discount: number;
    baggage_fees: number;
    points_used: number;
    points_value: number;
    total: number;
    amount_paid: number;
    points_earned: number;
  };
  payment: {
    id: string;
    method: string;
    status: string;
    transaction_id: string;
    card_last_four: string | null;
    currency: string;
    created_at: string;
  } | null;
  addons: {
    baggage: { tag_id: string; bag_type: string; weight_kg: number; fee: number }[];
    baggage_total: number;
  };
}

interface RefundHistoryRecord {
  id: string;
  booking_id: string;
  pnr: string;
  action_type: string;
  amount: number;
  currency: string;
  reason: string | null;
  refund_method: string | null;
  card_last_four: string | null;
  status: string;
  processed_at: string;
}

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
  cabin_class?: string;
}

export default function BookingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const bookingId = params.id as string;

  const [booking, setBooking] = useState<Booking | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  const [boardingPass, setBoardingPass] = useState<BoardingPass | null>(null);
  const [refundHistory, setRefundHistory] = useState<RefundHistoryRecord[]>([]);
  const [undoLoading, setUndoLoading] = useState(false);
  const boardingPassRef = useRef<HTMLDivElement>(null);
  const receiptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    const headers = { Authorization: `Bearer ${token}` };

    fetch(`${API_URL}/api/v1/bookings/${bookingId}`, { headers })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        setBooking(data);
        setLoading(false);
        if (data?.status === "checked_in") {
          fetch(`${API_URL}/api/v1/checkin`, {
            method: "POST",
            headers: { "Content-Type": "application/json", ...headers },
            body: JSON.stringify({ booking_id: bookingId, seat_preference: "window" }),
          })
            .then((r) => r.ok ? r.json() : null)
            .then((bp) => { if (bp) setBoardingPass(bp); });
        }
      })
      .catch(() => setLoading(false));

    fetch(`${API_URL}/api/v1/bookings/${bookingId}/receipt`, { headers })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setReceipt(data);
          fetch(`${API_URL}/api/v1/refunds/history/${data.booking.pnr}`, { headers })
            .then((r) => r.ok ? r.json() : null)
            .then((records) => { if (records) setRefundHistory(records); })
            .catch(() => {});
        }
      })
      .catch(() => {});
  }, [bookingId, router]);

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel this booking?")) return;
    setCancelling(true);
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = { Authorization: `Bearer ${token}` || "" };
      const res = await fetch(`${API_URL}/api/v1/bookings/${bookingId}/cancel`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        setBooking((prev) => prev ? { ...prev, status: "cancelled" } : prev);
        if (booking?.pnr) {
          const histRes = await fetch(`${API_URL}/api/v1/refunds/history/${booking.pnr}`, { headers });
          if (histRes.ok) {
            const records = await histRes.json();
            setRefundHistory(records);
          }
        }
      }
    } catch {}
    setCancelling(false);
  };


  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="animate-pulse"><Card className="p-6"><div className="h-32 bg-muted rounded" /></Card></div>
      </div>
    );
  }

  if (!booking) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground">Booking not found.</p>
        <Link href="/bookings"><Button variant="outline" className="mt-4">Back to Bookings</Button></Link>
      </div>
    );
  }

  const statusColor = booking.status === "confirmed" ? "default" : booking.status === "cancelled" ? "destructive" : "secondary";

  const flightDuration = receipt?.flight.departure && receipt?.flight.arrival
    ? (() => {
        const ms = new Date(receipt.flight.arrival!).getTime() - new Date(receipt.flight.departure!).getTime();
        const h = Math.floor(ms / 3600000);
        const m = Math.round((ms % 3600000) / 60000);
        return `${h}h ${m}m`;
      })()
    : null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center gap-2 mb-6">
        <Link href="/bookings" className="text-sm text-muted-foreground hover:text-foreground">&larr; Bookings</Link>
      </div>

      {/* Boarding Pass - shown for checked_in bookings */}
      {(booking.status === "checked_in" || boardingPass) && boardingPass && (
        <div ref={boardingPassRef}>
        <Card className="overflow-hidden border-2 border-blue-200 dark:border-blue-800 mb-6 animate-fade-in">
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
                      <div className="flex items-center gap-2">
                        {boardingPass.cabin_class && (
                          <Badge variant="secondary" className="text-[10px] capitalize">{boardingPass.cabin_class.replace("_", " ")}</Badge>
                        )}
                        {boardingPass.aircraft && <span className="text-[10px] text-muted-foreground">{boardingPass.aircraft}</span>}
                      </div>
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
                    <p className="font-semibold">{boardingPass.boarding_group}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Status</p>
                    <p className="font-semibold text-green-600">Confirmed</p>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-center justify-center sm:border-l sm:border-dashed sm:border-border/60 sm:pl-6">
                <div className="bg-white p-3 rounded-lg shadow-sm">
                  <QRCodeSVG value={boardingPass.boarding_pass_url} size={130} level="M" includeMargin={false} />
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
                      setBooking((prev) => prev ? { ...prev, status: "confirmed" } : prev);
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

      {/* Booking Confirmation */}
      <Card className="overflow-hidden">
        {/* Status Banner */}
        <div className={`px-6 py-3 flex items-center justify-between ${
          booking.status === "confirmed" ? "bg-green-600" :
          booking.status === "checked_in" ? "bg-blue-600" :
          booking.status === "cancelled" ? "bg-red-600" : "bg-slate-600"
        }`}>
          <div className="flex items-center gap-2">
            {booking.status === "confirmed" && (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
            {booking.status === "checked_in" && (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            )}
            {booking.status === "cancelled" && (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            <span className="text-white text-sm font-semibold capitalize">
              {booking.status === "confirmed" ? "Booking Confirmed" :
               booking.status === "checked_in" ? "Checked In" :
               booking.status === "cancelled" ? "Booking Cancelled" : booking.status}
            </span>
          </div>
          <span className="text-white/80 text-xs">
            {new Date(booking.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
          </span>
        </div>

        <div className="p-6">
          {/* PNR & QR Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Booking Reference</p>
              <h1 className="text-3xl font-bold font-mono tracking-wider mt-0.5">{booking.pnr}</h1>
              <p className="text-xs text-muted-foreground mt-1">
                Booked on {new Date(booking.created_at).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
              </p>
            </div>
            <div className="bg-white p-2 rounded-lg border border-border shadow-sm">
              <QRCodeSVG value={`https://autopilotairlines.com/bookings/${booking.id}`} size={72} level="M" includeMargin={false} />
            </div>
          </div>

          {/* Flight Route Card */}
          {receipt?.flight.flight_number && (
            <div className="rounded-xl border border-border bg-gradient-to-br from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 p-5 mb-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                    </svg>
                  </div>
                  <div>
                    <span className="font-mono font-bold text-sm">{receipt.flight.flight_number}</span>
                    <span className="text-xs text-muted-foreground ml-2">AutoPilot Airlines</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="capitalize text-[10px]">{(booking.cabin_class || "economy").replace("_", " ")}</Badge>
                  {receipt.flight.aircraft && (
                    <span className="text-[10px] text-muted-foreground">{receipt.flight.aircraft}</span>
                  )}
                </div>
              </div>

              {/* Route Visualization */}
              <div className="flex items-center gap-4 mb-4">
                <div className="text-center min-w-[70px]">
                  <p className="text-2xl font-bold">{receipt.flight.origin}</p>
                  {receipt.flight.departure && (
                    <p className="text-sm font-medium mt-0.5">
                      {new Date(receipt.flight.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center">
                    <div className="w-2.5 h-2.5 rounded-full border-2 border-blue-600" />
                    <div className="flex-1 relative mx-2">
                      <div className="border-t-2 border-dashed border-blue-300 dark:border-blue-700" />
                      {flightDuration && (
                        <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[10px] text-muted-foreground bg-background px-1">
                          {flightDuration}
                        </span>
                      )}
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                        </svg>
                      </div>
                    </div>
                    <div className="w-2.5 h-2.5 rounded-full bg-blue-600" />
                  </div>
                  <p className="text-center text-[10px] text-muted-foreground mt-1">Non-stop</p>
                </div>
                <div className="text-center min-w-[70px]">
                  <p className="text-2xl font-bold">{receipt.flight.destination}</p>
                  {receipt.flight.arrival && (
                    <p className="text-sm font-medium mt-0.5">
                      {new Date(receipt.flight.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                </div>
              </div>

              {/* Travel Date */}
              {receipt.booking.travel_date && (
                <div className="flex items-center gap-2 pt-3 border-t border-border/50">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                  </svg>
                  <span className="text-sm">
                    {new Date(receipt.booking.travel_date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Passenger Details */}
          <div className="rounded-lg border border-border p-4 mb-6">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-3">Passenger Details</p>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground text-xs">Full Name</p>
                <p className="font-medium">{booking.passenger_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">Email</p>
                <p className="font-medium">{booking.passenger_email}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">Cabin</p>
                <p className="font-medium capitalize">{(booking.cabin_class || "economy").replace("_", " ")}</p>
              </div>
              <div>
                <p className="text-muted-foreground text-xs">Ticket Status</p>
                <Badge variant={statusColor} className="capitalize mt-0.5">{booking.status.replace("_", " ")}</Badge>
              </div>
              {receipt?.booking.coupon_code && (
                <div>
                  <p className="text-muted-foreground text-xs">Coupon Applied</p>
                  <p className="font-medium font-mono text-green-600">{receipt.booking.coupon_code}</p>
                </div>
              )}
            </div>
          </div>

          {/* Booking Progress Timeline */}
          <div className="rounded-lg border border-border p-4 mb-6">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-3">Booking Timeline</p>
            {(() => {
              const cancellation = refundHistory.find(r => r.action_type === "cancellation");
              const refund = refundHistory.find(r => r.action_type === "refund");
              const isCancelled = booking.status === "cancelled" || booking.status === "refunded";

              const steps = [
                { label: "Booked", done: true, date: new Date(booking.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) },
                { label: "Confirmed", done: !isCancelled, date: new Date(booking.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) },
                ...(isCancelled
                  ? [
                      { label: "Cancelled", done: true, date: new Date(cancellation?.processed_at || booking.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) },
                      ...(refund || booking.status === "refunded"
                        ? [{ label: "Refunded", done: true, date: new Date(refund?.processed_at || booking.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) }]
                        : []),
                    ]
                  : [
                      { label: "Checked In", done: booking.status === "checked_in", date: booking.status === "checked_in" ? new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "" },
                      { label: "Boarded", done: false, date: "" },
                    ]),
              ];

              return (
                <div className="flex items-center justify-between">
                  {steps.map((step, i, arr) => (
                    <div key={step.label} className="flex items-center">
                      <div className="flex flex-col items-center">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          step.label === "Cancelled"
                            ? "bg-red-100 dark:bg-red-900/30 text-red-600"
                            : step.label === "Refunded"
                            ? "bg-amber-100 dark:bg-amber-900/30 text-amber-600"
                            : step.done
                            ? "bg-green-600 text-white"
                            : "bg-muted text-muted-foreground"
                        }`}>
                          {step.label === "Cancelled" ? (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          ) : step.label === "Refunded" ? (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                            </svg>
                          ) : step.done ? (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            i + 1
                          )}
                        </div>
                        <p className={`text-[10px] mt-1 ${step.done ? "text-foreground font-medium" : "text-muted-foreground"}`}>{step.label}</p>
                        {step.date && <p className="text-[9px] text-muted-foreground">{step.date}</p>}
                      </div>
                      {i < arr.length - 1 && (
                        <div className={`w-12 sm:w-16 h-0.5 mx-1 mb-6 ${
                          step.label === "Cancelled" || step.label === "Refunded"
                            ? "bg-red-200 dark:bg-red-900/50"
                            : step.done && arr[i + 1].done
                            ? "bg-green-600"
                            : "bg-muted"
                        }`} />
                      )}
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>

          {/* Fare Summary (compact) */}
          {receipt && (receipt.payment || receipt.pricing.amount_paid > 0 || receipt.pricing.total > 0) && (
            <div className="rounded-lg border border-border p-4 mb-6">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-3">Fare Summary</p>
              <div className="space-y-1.5 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Fare + taxes</span>
                  <span>${receipt.pricing.subtotal.toFixed(2)}</span>
                </div>
                {receipt.pricing.coupon_discount > 0 && (
                  <div className="flex items-center justify-between text-green-600">
                    <span>Discount ({receipt.pricing.coupon_code})</span>
                    <span>-${receipt.pricing.coupon_discount.toFixed(2)}</span>
                  </div>
                )}
                {receipt.addons.baggage_total > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Baggage</span>
                    <span>${receipt.addons.baggage_total.toFixed(2)}</span>
                  </div>
                )}
                {receipt.pricing.points_used > 0 && (
                  <div className="flex items-center justify-between text-amber-600">
                    <span>Points redeemed ({receipt.pricing.points_used.toLocaleString()} pts)</span>
                    <span>-${receipt.pricing.points_value.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-border">
                  <span className="font-semibold">{receipt.payment ? "Amount paid" : "Total fare"}</span>
                  <span className="text-lg font-bold">
                    ${(receipt.payment ? receipt.pricing.amount_paid : receipt.pricing.total).toFixed(2)}
                    <span className="text-xs font-normal text-muted-foreground ml-1">{receipt.payment?.currency || "USD"}</span>
                  </span>
                </div>
                {!receipt.payment && (
                  <p className="text-xs text-muted-foreground italic">Payment pending</p>
                )}
              </div>
              {receipt.pricing.points_earned > 0 && (
                <p className="text-xs text-amber-600 mt-2">+{receipt.pricing.points_earned.toLocaleString()} SkyPoints earned on this booking</p>
              )}
            </div>
          )}

          {/* Important Information */}
          <div className="rounded-lg bg-muted/30 border border-border p-4 mb-6">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Important Information</p>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              <li>Check-in opens 48 hours before departure</li>
              <li>Please arrive at the airport at least 2 hours before domestic / 3 hours before international flights</li>
              <li>Carry a valid photo ID matching the name on your booking</li>
              <li>Baggage allowance: {(booking.cabin_class || "economy") === "business" ? "2x32kg checked + 2x10kg cabin" : (booking.cabin_class || "economy") === "premium_economy" ? "1x23kg checked + 1x10kg cabin" : "1x7kg cabin (checked bags available for purchase)"}</li>
            </ul>
          </div>

          {/* Cancellation & Refund History */}
          {refundHistory.length > 0 && (
            <div className="rounded-lg border border-border p-4 mb-6">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-3">Transaction History</p>
              <div className="space-y-2">
                {refundHistory.map((record) => (
                  <div key={record.id} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
                    <div className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                      record.action_type === "cancellation"
                        ? "bg-red-100 dark:bg-red-900/30"
                        : "bg-amber-100 dark:bg-amber-900/30"
                    }`}>
                      {record.action_type === "cancellation" ? (
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">
                            {record.action_type === "cancellation" ? "Booking Cancelled" : "Refund Processed"}
                          </span>
                          <Badge
                            variant={record.action_type === "cancellation" ? "destructive" : "secondary"}
                            className="text-[10px]"
                          >
                            {record.status}
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(record.processed_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-xs text-muted-foreground">
                        {record.action_type === "refund" && (
                          <span className="font-medium text-foreground">${record.amount.toFixed(2)} {record.currency}</span>
                        )}
                        {record.refund_method && record.action_type === "refund" && (
                          <span>
                            → {record.refund_method === "card" ? "Card" : record.refund_method}
                            {record.card_last_four && <span className="font-mono ml-1">••••{record.card_last_four}</span>}
                          </span>
                        )}
                        {record.reason && <span>{record.reason}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap gap-2 pt-4 border-t border-border">
            {booking.status === "confirmed" && !boardingPass && (() => {
              const dep = receipt?.flight.departure;
              const hoursUntil = dep ? (new Date(dep).getTime() - Date.now()) / (1000 * 60 * 60) : null;
              const checkinOpen = hoursUntil !== null && hoursUntil <= 48;
              return (
                <>
                  {checkinOpen ? (
                    <Link href={`/checkin?pnr=${booking.pnr}`}>
                      <Button>Check In</Button>
                    </Link>
                  ) : hoursUntil !== null ? (
                    <Button disabled title="Check-in opens 48 hours before departure">
                      Check-in not open yet
                    </Button>
                  ) : null}
                  <Button variant="outline" onClick={handleCancel} disabled={cancelling}>
                    {cancelling ? "Cancelling..." : "Cancel Booking"}
                  </Button>
                </>
              );
            })()}
            {booking.status === "checked_in" && !boardingPass && (
              <Link href={`/checkin?pnr=${booking.pnr}`}>
                <Button>View Boarding Pass</Button>
              </Link>
            )}
            {receipt && (
              <>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (!receiptRef.current) return;
                    const viewWindow = window.open("", "_blank");
                    if (!viewWindow) return;
                    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
                      .map((el) => el.outerHTML)
                      .join("\n");
                    const content = receiptRef.current.innerHTML;
                    viewWindow.document.write(`<!DOCTYPE html><html><head><title>Receipt - ${booking.pnr} - AutoPilot Airlines</title>${styles}<style>
                      body { padding: 40px; background: white; font-family: system-ui, sans-serif; }
                      button { display: none !important; }
                    </style></head><body><div class="max-w-2xl mx-auto">${content}</div></body></html>`);
                    viewWindow.document.close();
                  }}
                >
                  View Receipt
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (!receiptRef.current) return;
                    const printWindow = window.open("", "_blank");
                    if (!printWindow) return;
                    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
                      .map((el) => el.outerHTML)
                      .join("\n");
                    const content = receiptRef.current.innerHTML;
                    printWindow.document.write(`<!DOCTYPE html><html><head><title>Receipt - ${booking.pnr} - AutoPilot Airlines</title>${styles}<style>
                      body { padding: 40px; background: white; font-family: system-ui, sans-serif; }
                      @media print { body { padding: 20px; } button { display: none !important; } }
                      button { display: none !important; }
                    </style></head><body><div class="max-w-2xl mx-auto">${content}</div></body></html>`);
                    printWindow.document.close();
                    setTimeout(() => { printWindow.print(); }, 600);
                  }}
                >
                  Print Receipt
                </Button>
              </>
            )}
            <Link href="/bookings">
              <Button variant="ghost" size="sm">All Bookings</Button>
            </Link>
          </div>
        </div>
      </Card>

      {/* Receipt (hidden, rendered for print) */}
      {receipt && (
        <div ref={receiptRef} className="hidden">
        <Card className="p-6 mt-6">
          {/* Receipt Header */}
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                </svg>
              </div>
              <div>
                <p className="font-bold text-sm">AutoPilot Airlines</p>
                <p className="text-[10px] text-muted-foreground">IATA: AP | ICAO: APA | DOT: 1247</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Payment Receipt</p>
              <p className="font-mono text-xs text-muted-foreground mt-0.5">
                #{receipt.payment?.transaction_id || receipt.booking.pnr}
              </p>
            </div>
          </div>

          <div className="border-t border-dashed border-border my-4" />

          {/* Passenger & Booking Info */}
          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div>
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">Billed To</p>
              <p className="font-semibold">{receipt.booking.passenger_name}</p>
              <p className="text-muted-foreground text-xs">{receipt.booking.passenger_email}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1">Booking Reference</p>
              <p className="font-mono font-bold text-lg">{receipt.booking.pnr}</p>
              <p className="text-xs text-muted-foreground">
                Issued: {new Date(receipt.booking.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
              </p>
            </div>
          </div>

          <div className="border-t border-border my-4" />

          {/* Itinerary */}
          <div className="mb-4">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Itinerary</p>
            {receipt.flight.flight_number && (
              <div className="p-3 rounded-lg bg-muted/30 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-sm">{receipt.flight.flight_number}</span>
                    <Badge variant="secondary" className="capitalize text-[10px]">{receipt.booking.cabin_class.replace("_", " ")}</Badge>
                  </div>
                  {receipt.flight.aircraft && <span className="text-[10px] text-muted-foreground">{receipt.flight.aircraft}</span>}
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-lg font-bold">{receipt.flight.origin}</p>
                    {receipt.flight.departure && (
                      <p className="text-[10px] text-muted-foreground">{new Date(receipt.flight.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                    )}
                  </div>
                  <div className="flex-1 flex items-center">
                    <div className="w-2 h-2 rounded-full border-2 border-blue-600" />
                    <div className="flex-1 border-t-2 border-dashed border-muted-foreground/30 mx-1" />
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                    </svg>
                    <div className="flex-1 border-t-2 border-dashed border-muted-foreground/30 mx-1" />
                    <div className="w-2 h-2 rounded-full bg-blue-600" />
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold">{receipt.flight.destination}</p>
                    {receipt.flight.arrival && (
                      <p className="text-[10px] text-muted-foreground">{new Date(receipt.flight.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                    )}
                  </div>
                </div>
                {receipt.booking.travel_date && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Travel Date: {new Date(receipt.booking.travel_date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="border-t border-border my-4" />

          {/* Fare Breakdown */}
          <div className="mb-4">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Fare Breakdown</p>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Air fare &mdash; {receipt.booking.cabin_class.replace("_", " ")} class (1 pax)</span>
                <span>${receipt.pricing.base_fare.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Government taxes & carrier-imposed fees</span>
                <span>${receipt.pricing.taxes.toFixed(2)}</span>
              </div>
              {receipt.pricing.coupon_discount > 0 && (
                <div className="flex justify-between text-green-600">
                  <span>Promotional discount ({receipt.pricing.coupon_code})</span>
                  <span>-${receipt.pricing.coupon_discount.toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Add-ons */}
          {receipt.addons.baggage.length > 0 && (
            <div className="mb-4">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Ancillary Services</p>
              <div className="space-y-2 text-sm">
                {receipt.addons.baggage.map((bag) => (
                  <div key={bag.tag_id} className="flex justify-between">
                    <span className="capitalize">{bag.bag_type} baggage &mdash; {bag.weight_kg}kg (Tag: {bag.tag_id})</span>
                    <span>${bag.fee.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Points Redeemed */}
          {receipt.pricing.points_used > 0 && (
            <div className="mb-4">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Loyalty Redemption</p>
              <div className="flex justify-between text-sm text-amber-600">
                <span>{receipt.pricing.points_used.toLocaleString()} points redeemed @ $0.10/pt</span>
                <span>-${receipt.pricing.points_value.toFixed(2)}</span>
              </div>
            </div>
          )}

          <div className="border-t-2 border-border my-4" />

          {/* Totals */}
          <div className="space-y-1 text-sm mb-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Subtotal</span>
              <span>${receipt.pricing.subtotal.toFixed(2)}</span>
            </div>
            {receipt.pricing.coupon_discount > 0 && (
              <div className="flex justify-between text-green-600">
                <span>Discount{receipt.pricing.coupon_code ? ` (${receipt.pricing.coupon_code})` : ""}</span>
                <span>-${receipt.pricing.coupon_discount.toFixed(2)}</span>
              </div>
            )}
            {receipt.addons.baggage_total > 0 && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Ancillary services</span>
                <span>${receipt.addons.baggage_total.toFixed(2)}</span>
              </div>
            )}
            {receipt.pricing.points_value > 0 && (
              <div className="flex justify-between text-amber-600">
                <span>Points applied</span>
                <span>-${receipt.pricing.points_value.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between font-bold text-base pt-2 border-t border-border">
              <span>Amount Charged</span>
              <span>${receipt.pricing.amount_paid.toFixed(2)} {receipt.payment?.currency || "USD"}</span>
            </div>
          </div>

          <div className="border-t border-border my-4" />

          {/* Payment Details */}
          {receipt.payment && (
            <div className="mb-4">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-2">Payment Information</p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Method</span>
                  <span className="font-medium capitalize">{receipt.payment.method.replace(/_/g, " ")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <span className="font-medium capitalize text-green-600">{receipt.payment.status}</span>
                </div>
                {receipt.payment.card_last_four && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Card ending</span>
                    <span className="font-mono">**** **** **** {receipt.payment.card_last_four}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Transaction ID</span>
                  <span className="font-mono text-xs">{receipt.payment.transaction_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Date</span>
                  <span>{new Date(receipt.payment.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Currency</span>
                  <span>{receipt.payment.currency}</span>
                </div>
              </div>
            </div>
          )}

          {/* Points Earned */}
          {receipt.pricing.points_earned > 0 && (
            <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 mb-4">
              <div className="flex items-center gap-2 text-sm">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
                <span className="font-medium text-amber-800 dark:text-amber-300">
                  +{receipt.pricing.points_earned.toLocaleString()} SkyPoints earned
                </span>
                <span className="text-xs text-amber-600 dark:text-amber-400">(value: ${(receipt.pricing.points_earned * 0.10).toFixed(2)})</span>
              </div>
            </div>
          )}

          <div className="border-t border-dashed border-border my-4" />

          {/* Fine Print */}
          <div className="space-y-2 text-[10px] text-muted-foreground leading-relaxed">
            <p className="font-medium text-xs text-foreground">Terms & Conditions</p>
            <p>
              This document serves as your official payment receipt and e-ticket confirmation for the above itinerary.
              Please retain this receipt for your records and present it at check-in if requested.
            </p>
            <p>
              <span className="font-medium">Cancellation Policy:</span> Cancellations made more than 24 hours before departure
              are eligible for a full refund minus a ${receipt.booking.cabin_class === "business" ? "50.00" : "25.00"} processing fee.
              Cancellations within 24 hours of departure are non-refundable. No-shows forfeit the full fare.
            </p>
            <p>
              <span className="font-medium">Changes & Modifications:</span> Date/time changes are permitted up to 4 hours before
              departure subject to a ${receipt.booking.cabin_class === "business" ? "0" : "35.00"} change fee plus any fare difference.
              Name corrections (up to 3 characters) are free; full name changes require a new booking.
            </p>
            <p>
              <span className="font-medium">Baggage:</span> Economy class includes 1 carry-on bag (7kg) and 1 personal item.
              Premium Economy includes 1 carry-on (10kg) + 1 checked bag (23kg).
              Business class includes 2 carry-ons (10kg each) + 2 checked bags (32kg each).
              Excess baggage fees apply at the airport.
            </p>
            <p>
              <span className="font-medium">Loyalty Program:</span> SkyPoints earned on this transaction will be credited to your
              account within 72 hours of travel completion. Points are non-transferable and expire 24 months from the date of accrual.
              Tier qualification is based on calendar-year activity.
            </p>
            <p>
              <span className="font-medium">Liability:</span> Carriage is subject to the Montreal Convention (1999) and applicable
              local regulations. AutoPilot Airlines&apos; liability for checked baggage is limited to 1,288 SDR per passenger.
              The airline reserves the right to substitute aircraft or alter schedules due to operational requirements.
            </p>
            <p className="pt-2 border-t border-border/50">
              AutoPilot Airlines Inc. &bull; 1 Aviation Boulevard, Sky City, SC 10001 &bull;
              IATA Designator: AP &bull; Airline Code: 247 &bull; Tax ID: 84-2941837 &bull;
              Customer Service: 1-800-FLY-AUTO (1-800-359-2886) &bull; support@autopilotairlines.com
            </p>
            <p className="text-center italic">
              Thank you for flying with AutoPilot Airlines. This is a computer-generated receipt and does not require a signature.
            </p>
          </div>
        </Card>
        </div>
      )}
    </div>
  );
}
