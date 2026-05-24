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
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  const [boardingPass, setBoardingPass] = useState<BoardingPass | null>(null);
  const [undoLoading, setUndoLoading] = useState(false);
  const boardingPassRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    fetch(`${API_URL}/api/v1/bookings/${bookingId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        setBooking(data);
        setLoading(false);
        if (data?.status === "checked_in") {
          const headers: Record<string, string> = { "Content-Type": "application/json" };
          if (token) headers["Authorization"] = `Bearer ${token}`;
          fetch(`${API_URL}/api/v1/checkin`, {
            method: "POST",
            headers,
            body: JSON.stringify({ booking_id: bookingId, seat_preference: "window" }),
          })
            .then((r) => r.ok ? r.json() : null)
            .then((bp) => { if (bp) setBoardingPass(bp); });
        }
      })
      .catch(() => setLoading(false));
  }, [bookingId, router]);

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel this booking?")) return;
    setCancelling(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/v1/bookings/${bookingId}/cancel`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setBooking((prev) => prev ? { ...prev, status: "cancelled" } : prev);
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

      {/* Booking Details */}
      <Card className="p-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold font-mono">{booking.pnr}</h1>
            <p className="text-sm text-muted-foreground mt-1">Booking Reference</p>
          </div>
          <Badge variant={statusColor} className="capitalize">{booking.status.replace("_", " ")}</Badge>
        </div>

        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-muted-foreground text-xs mb-0.5">Passenger</p>
              <p className="font-medium">{booking.passenger_name}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-0.5">Email</p>
              <p>{booking.passenger_email}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-muted-foreground text-xs mb-0.5">Cabin Class</p>
              <p className="font-medium capitalize">{(booking.cabin_class || "economy").replace("_", " ")}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-0.5">Booked On</p>
              <p>{new Date(booking.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs mb-0.5">Booking ID</p>
              <p className="font-mono text-xs">{booking.id}</p>
            </div>
          </div>
        </div>

        {/* Check-in section for confirmed bookings */}
        {booking.status === "confirmed" && !boardingPass && (
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex gap-2">
              <Link href={`/checkin?pnr=${booking.pnr}`}>
                <Button>Check In</Button>
              </Link>
              <Button variant="outline" onClick={handleCancel} disabled={cancelling}>
                {cancelling ? "Cancelling..." : "Cancel Booking"}
              </Button>
            </div>
          </div>
        )}

        {/* Actions for checked_in without boarding pass loaded */}
        {booking.status === "checked_in" && !boardingPass && (
          <div className="mt-6 pt-6 border-t border-border">
            <p className="text-sm text-green-600 font-medium">Already checked in</p>
            <Link href={`/checkin?pnr=${booking.pnr}`}>
              <Button variant="outline" size="sm" className="mt-2">View Boarding Pass</Button>
            </Link>
          </div>
        )}

        {/* Actions for cancelled */}
        {booking.status === "cancelled" && (
          <div className="mt-6 pt-6 border-t border-border">
            <p className="text-sm text-destructive">This booking has been cancelled.</p>
          </div>
        )}
      </Card>
    </div>
  );
}
