"use client";

import { useState, useEffect, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  base_price: number;
  price: number;
  available_seats: number;
  total_seats: number;
  cabin_classes?: Record<string, CabinAvailability> | null;
}

interface BookingResult {
  id: string;
  pnr: string;
  passenger_name: string;
  passenger_email: string;
  status: string;
}

interface Passenger {
  name: string;
  email: string;
  age: string;
}

type Step = "details" | "payment" | "confirmation";

export default function BookPage() {
  return (
    <Suspense fallback={<div className="max-w-3xl mx-auto px-4 py-8"><Card className="p-6"><div className="h-40 bg-muted rounded animate-pulse" /></Card></div>}>
      <BookPageContent />
    </Suspense>
  );
}

function BookPageContent() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const flightId = params.flightId as string;
  const travelDate = searchParams.get("date") || "";
  const returnFlightId = searchParams.get("returnFlight") || "";
  const returnTravelDate = searchParams.get("returnDate") || "";
  const isRoundTrip = !!returnFlightId;

  const outboundSegmentIds = flightId.split("_");
  const isMultiStop = outboundSegmentIds.length > 1;
  const returnSegmentIds = returnFlightId ? returnFlightId.split("_") : [];
  const isReturnMultiStop = returnSegmentIds.length > 1;

  const [flight, setFlight] = useState<Flight | null>(null);
  const [outboundSegments, setOutboundSegments] = useState<Flight[]>([]);
  const [returnFlight, setReturnFlight] = useState<Flight | null>(null);
  const [returnSegmentsList, setReturnSegmentsList] = useState<Flight[]>([]);
  const [step, setStep] = useState<Step>("details");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [bookings, setBookings] = useState<BookingResult[]>([]);
  const [returnBookings, setReturnBookings] = useState<BookingResult[]>([]);

  const [passengers, setPassengers] = useState<Passenger[]>([{ name: "", email: "", age: "" }]);
  const [phone, setPhone] = useState("");

  const [coupon, setCoupon] = useState("");
  const [discount, setDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState("");
  const [availableOffers, setAvailableOffers] = useState<{ code: string; discount_percent: number; description: string; type: string; min_passengers?: number }[]>([]);

  const [cabinClass, setCabinClass] = useState<"economy" | "premium_economy" | "business">("economy");

  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");

  const [loyaltyPoints, setLoyaltyPoints] = useState(0);
  const [pointsEarned12m, setPointsEarned12m] = useState(0);
  const [usePoints, setUsePoints] = useState(false);
  const [pointsToUse, setPointsToUse] = useState(0);

  const [currentUser, setCurrentUser] = useState<{ name: string; email: string; date_of_birth?: string } | null>(null);
  const [savedPassengers, setSavedPassengers] = useState<Passenger[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push(`/login`);
      return;
    }
    const dateParam = travelDate ? `?date=${travelDate}` : "";

    const mergeCabinClasses = (segments: Flight[]): Record<string, CabinAvailability> | null => {
      const allCc = segments.map(s => s.cabin_classes).filter(Boolean) as Record<string, CabinAvailability>[];
      if (allCc.length === 0) return null;
      const merged: Record<string, CabinAvailability> = {};
      for (const cabin of ["economy", "premium_economy", "business"] as const) {
        const entries = allCc.map(cc => cc[cabin]).filter(Boolean);
        if (entries.length === 0) continue;
        merged[cabin] = {
          seats: Math.min(...entries.map(e => e.seats)),
          available: Math.min(...entries.map(e => e.available)),
          price: Math.round(entries.reduce((sum, e) => sum + e.price, 0) * 100) / 100,
        };
      }
      return Object.keys(merged).length > 0 ? merged : null;
    };

    const outboundFetch = isMultiStop
      ? Promise.all(outboundSegmentIds.map(id => fetch(`${API_URL}/api/v1/flights/${id}${dateParam}`).then(r => r.ok ? r.json() : null)))
          .then(segments => {
            const valid = segments.filter(Boolean) as Flight[];
            if (valid.length === 0) return null;
            setOutboundSegments(valid);
            return {
              id: flightId,
              flight_number: valid.map(s => s.flight_number).join("+"),
              origin: valid[0].origin,
              destination: valid[valid.length - 1].destination,
              departure: valid[0].departure,
              arrival: valid[valid.length - 1].arrival,
              aircraft: valid.map(s => s.aircraft).join(" / "),
              base_price: valid.reduce((sum, s) => sum + s.base_price, 0),
              price: valid.reduce((sum, s) => sum + s.price, 0),
              available_seats: Math.min(...valid.map(s => s.available_seats)),
              total_seats: Math.min(...valid.map(s => s.total_seats)),
              cabin_classes: mergeCabinClasses(valid),
            } as Flight;
          })
      : fetch(`${API_URL}/api/v1/flights/${flightId}${dateParam}`).then(r => r.ok ? r.json() : null);

    const retDateParam = returnTravelDate ? `?date=${returnTravelDate}` : "";
    const returnFetch = isRoundTrip
      ? isReturnMultiStop
        ? Promise.all(returnSegmentIds.map(id => fetch(`${API_URL}/api/v1/flights/${id}${retDateParam}`).then(r => r.ok ? r.json() : null)))
            .then(segments => {
              const valid = segments.filter(Boolean) as Flight[];
              if (valid.length === 0) return null;
              setReturnSegmentsList(valid);
              return {
                id: returnFlightId,
                flight_number: valid.map(s => s.flight_number).join("+"),
                origin: valid[0].origin,
                destination: valid[valid.length - 1].destination,
                departure: valid[0].departure,
                arrival: valid[valid.length - 1].arrival,
                aircraft: valid.map(s => s.aircraft).join(" / "),
                base_price: valid.reduce((sum, s) => sum + s.base_price, 0),
                price: valid.reduce((sum, s) => sum + s.price, 0),
                available_seats: Math.min(...valid.map(s => s.available_seats)),
                total_seats: Math.min(...valid.map(s => s.total_seats)),
                cabin_classes: mergeCabinClasses(valid),
              } as Flight;
            })
        : fetch(`${API_URL}/api/v1/flights/${returnFlightId}${retDateParam}`).then(r => r.ok ? r.json() : null)
      : Promise.resolve(null);

    Promise.all([outboundFetch, returnFetch])
      .then(([outData, retData]) => {
        setFlight(outData);
        if (retData) setReturnFlight(retData);
        setLoading(false);
      })
      .catch(() => setLoading(false));

    fetch(`${API_URL}/api/v1/bookings/coupons/available`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.offers) setAvailableOffers(data.offers); })
      .catch(() => {});

    fetch(`${API_URL}/api/v1/loyalty/balance`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setLoyaltyPoints(data.points);
          setPointsEarned12m(data.points_earned_12m);
        }
      })
      .catch(() => {});

    fetch(`${API_URL}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setCurrentUser({ name: data.name, email: data.email, date_of_birth: data.date_of_birth || undefined });
          if (data.phone) setPhone(data.phone);
        }
      })
      .catch(() => {});

    try {
      const saved = localStorage.getItem("savedPassengers");
      if (saved) setSavedPassengers(JSON.parse(saved));
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flightId, returnFlightId, router, travelDate, returnTravelDate, isRoundTrip]);

  const addPassenger = () => {
    if (passengers.length >= (getClassAvailable(flight) || 10)) return;
    setPassengers([...passengers, { name: "", email: "", age: "" }]);
  };

  const removePassenger = (index: number) => {
    if (passengers.length <= 1) return;
    setPassengers(passengers.filter((_, i) => i !== index));
    if (discount > 0) {
      setDiscount(0);
      setCoupon("");
      setCouponMsg("");
    }
  };

  const updatePassenger = (index: number, field: keyof Passenger, value: string) => {
    const updated = [...passengers];
    updated[index] = { ...updated[index], [field]: value };
    setPassengers(updated);
  };

  const fillSelf = (index: number) => {
    if (!currentUser) return;
    let age = "";
    if (currentUser.date_of_birth) {
      const dob = new Date(currentUser.date_of_birth);
      const today = new Date();
      let a = today.getFullYear() - dob.getFullYear();
      if (today.getMonth() < dob.getMonth() || (today.getMonth() === dob.getMonth() && today.getDate() < dob.getDate())) a--;
      age = String(a);
    }
    const updated = [...passengers];
    updated[index] = { name: currentUser.name, email: currentUser.email, age };
    setPassengers(updated);
  };

  const fillSavedPassenger = (index: number, saved: Passenger) => {
    const updated = [...passengers];
    updated[index] = { name: saved.name, email: saved.email, age: saved.age || "" };
    setPassengers(updated);
  };

  const savePassengerToList = (pax: Passenger) => {
    const existing = savedPassengers.find(
      (s) => s.email.toLowerCase() === pax.email.toLowerCase()
    );
    if (existing) return;
    const updated = [...savedPassengers, pax];
    setSavedPassengers(updated);
    localStorage.setItem("savedPassengers", JSON.stringify(updated));
  };

  const removeSavedPassenger = (email: string) => {
    const updated = savedPassengers.filter(
      (s) => s.email.toLowerCase() !== email.toLowerCase()
    );
    setSavedPassengers(updated);
    localStorage.setItem("savedPassengers", JSON.stringify(updated));
  };

  const applyCoupon = async () => {
    if (!coupon.trim()) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/v1/bookings/coupons/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          code: coupon,
          passengers: passengers.length,
          flight_id: outboundSegmentIds[0],
          cabin_class: cabinClass,
          subtotal: perPersonPrice * passengers.length,
        }),
      });
      const data = await res.json();
      if (data.valid) {
        setDiscount(data.discount_percent);
        setCouponMsg(`${data.description} applied!`);
      } else {
        setDiscount(0);
        setCouponMsg(data.description || "Invalid coupon code");
      }
    } catch {
      setCouponMsg("Error validating coupon");
    }
  };

  const getClassPrice = (f: Flight | null) => {
    if (!f) return 0;
    if (f.cabin_classes && f.cabin_classes[cabinClass]) return f.cabin_classes[cabinClass].price;
    const classMultiplier = { economy: 1, premium_economy: 1.5, business: 2.5 }[cabinClass];
    return (f.price || f.base_price) * classMultiplier;
  };
  const outboundPrice = getClassPrice(flight);
  const returnPrice = getClassPrice(returnFlight);
  const perPersonPrice = outboundPrice + returnPrice;
  const subtotal = perPersonPrice * passengers.length;
  const afterDiscount = subtotal * (1 - discount / 100);
  const pointsValue = usePoints ? Math.min(pointsToUse * 0.01, afterDiscount) : 0;
  const finalPrice = afterDiscount - pointsValue;

  const getClassAvailable = (f: Flight | null) => {
    if (!f) return 0;
    if (f.cabin_classes && f.cabin_classes[cabinClass]) return f.cabin_classes[cabinClass].available;
    return f.available_seats;
  };

  const allPassengersValid = passengers.every(p => p.name.trim() && p.email.trim() && p.age.trim() && parseInt(p.age) > 0);

  const handleBook = async () => {
    setSubmitting(true);
    try {
      const token = localStorage.getItem("token");
      const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

      const bookSegments = async (segmentIds: string[], date: string | undefined) => {
        const results: BookingResult[] = [];
        for (const pax of passengers) {
          for (const segId of segmentIds) {
            const res = await fetch(`${API_URL}/api/v1/bookings`, {
              method: "POST",
              headers,
              body: JSON.stringify({
                flight_id: segId,
                passenger_name: pax.name,
                passenger_email: pax.email,
                travel_date: date || undefined,
                cabin_class: cabinClass,
                coupon_code: discount > 0 ? coupon : undefined,
              }),
            });
            if (!res.ok) throw new Error("Booking failed");
            if (segId === segmentIds[0]) {
              results.push(await res.json());
            } else {
              await res.json();
            }
          }
        }
        return results;
      };

      const outboundBookings = await bookSegments(outboundSegmentIds, travelDate);
      setBookings(outboundBookings);

      if (isRoundTrip) {
        const retBookings = await bookSegments(returnSegmentIds.length > 0 ? returnSegmentIds : [returnFlightId], returnTravelDate);
        setReturnBookings(retBookings);
      }

      await fetch(`${API_URL}/api/v1/payments`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          booking_id: outboundBookings[0].id,
          amount: afterDiscount,
          method: finalPrice <= 0 ? "points" : "credit_card",
          card_number: finalPrice > 0 ? cardNumber : undefined,
          points_used: usePoints ? pointsToUse : 0,
        }),
      });

      setStep("confirmation");
    } catch {
      alert("Booking failed. Please try again.");
    }
    setSubmitting(false);
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 bg-muted rounded" />
          <Card className="p-6"><div className="h-40 bg-muted rounded" /></Card>
        </div>
      </div>
    );
  }

  if (!flight) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground">Flight not found.</p>
        <Link href="/"><Button variant="outline" className="mt-4">Back to Search</Button></Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Progress Steps */}
      <div className="flex items-center gap-2 mb-8">
        {(["details", "payment", "confirmation"] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${
              step === s ? "bg-blue-600 text-white" : i < ["details", "payment", "confirmation"].indexOf(step) ? "bg-green-500 text-white" : "bg-muted text-muted-foreground"
            }`}>
              {i < ["details", "payment", "confirmation"].indexOf(step) ? "✓" : i + 1}
            </div>
            <span className={`text-sm capitalize ${step === s ? "font-medium" : "text-muted-foreground"}`}>{s}</span>
            {i < 2 && <div className="w-8 h-px bg-border" />}
          </div>
        ))}
      </div>

      {/* Cabin Class Selection */}
      <Card className="p-5 mb-6">
        <h2 className="font-semibold mb-3">Select Cabin Class</h2>
        <div className="grid grid-cols-3 gap-3">
          {([
            { key: "economy" as const, label: "Economy", bags: "1 checked (23kg)", carryon: "1 carry-on (7kg)", seat: "Standard seat" },
            { key: "premium_economy" as const, label: "Premium Economy", bags: "2 checked (23kg)", carryon: "1 carry-on (10kg)", seat: "Extra legroom" },
            { key: "business" as const, label: "Business", bags: "2 checked (32kg)", carryon: "2 carry-ons (10kg)", seat: "Lie-flat seat" },
          ]).map((cls) => {
            const cabinInfo = flight.cabin_classes?.[cls.key];
            const notOffered = flight.cabin_classes && !cabinInfo;
            const available = cabinInfo?.available ?? flight.available_seats;
            const price = cabinInfo?.price;
            const soldOut = notOffered || (cabinInfo && cabinInfo.available === 0);
            return (
              <button
                key={cls.key}
                type="button"
                onClick={() => !soldOut && setCabinClass(cls.key)}
                disabled={!!soldOut}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  soldOut ? "border-border opacity-50 cursor-not-allowed" :
                  cabinClass === cls.key
                    ? "border-blue-600 bg-blue-50 dark:bg-blue-950/30"
                    : "border-border hover:border-blue-300"
                }`}
              >
                <p className="font-semibold text-sm">{cls.label}</p>
                <p className="text-xs text-muted-foreground mt-1">{cls.seat}</p>
                <div className="mt-2 space-y-0.5">
                  <p className="text-[10px] text-muted-foreground">{cls.bags}</p>
                  <p className="text-[10px] text-muted-foreground">{cls.carryon}</p>
                </div>
                {notOffered ? (
                  <p className="mt-2 text-[10px] text-muted-foreground">Not available on this aircraft</p>
                ) : price !== undefined ? (
                  <div className="mt-2">
                    <p className="text-sm font-bold text-blue-600">${price.toFixed(0)}</p>
                    <p className="text-[10px] text-muted-foreground">{cabinInfo && cabinInfo.available === 0 ? "Sold out" : `${available} seats left`}</p>
                  </div>
                ) : (
                  <p className="mt-2 text-[10px] text-muted-foreground">{available} seats</p>
                )}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Flight Summary */}
      <div className="space-y-3 mb-6">
        <Card className="p-4 bg-muted/30">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div>
                <p className="font-semibold">{flight.flight_number}</p>
                <p className="text-xs text-muted-foreground">{flight.aircraft}</p>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium">{flight.origin}</span>
                <span className="text-muted-foreground">&rarr;</span>
                <span className="font-medium">{flight.destination}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {new Date(flight.departure).toLocaleDateString()} at {new Date(flight.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
            </div>
            <div className="text-right">
              {isRoundTrip && <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Outbound</p>}
              <p className="text-lg font-bold text-blue-600">${outboundPrice.toFixed(2)}</p>
              <p className="text-[10px] text-muted-foreground">per person</p>
            </div>
          </div>
          {outboundSegments.length > 1 && (
            <div className="mt-3 pt-3 border-t border-border space-y-2">
              <p className="text-[10px] uppercase tracking-wide font-medium text-muted-foreground">{outboundSegments.length} Segments</p>
              {outboundSegments.map((seg, i) => (
                <div key={seg.id}>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-medium">{seg.flight_number}</span>
                      <span>{seg.origin}</span>
                      <span className="text-muted-foreground">&rarr;</span>
                      <span>{seg.destination}</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{new Date(seg.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} - {new Date(seg.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                      <span className="font-medium text-foreground">${getClassPrice(seg).toFixed(2)}</span>
                    </div>
                  </div>
                  {i < outboundSegments.length - 1 && (() => {
                    const layoverMs = new Date(outboundSegments[i + 1].departure).getTime() - new Date(seg.arrival).getTime();
                    const layoverH = Math.floor(layoverMs / 3600000);
                    const layoverM = Math.round((layoverMs % 3600000) / 60000);
                    return (
                      <div className="flex items-center gap-2 py-1 pl-4">
                        <div className="w-3 border-l-2 border-dashed border-muted-foreground/40 h-4" />
                        <span className="text-[10px] text-muted-foreground">Layover in {seg.destination} &middot; {layoverH > 0 ? `${layoverH}h ` : ""}{layoverM}m</span>
                      </div>
                    );
                  })()}
                </div>
              ))}
            </div>
          )}
        </Card>

        {isRoundTrip && returnFlight && (
          <Card className="p-4 bg-muted/30">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <div>
                  <p className="font-semibold">{returnFlight.flight_number}</p>
                  <p className="text-xs text-muted-foreground">{returnFlight.aircraft}</p>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{returnFlight.origin}</span>
                  <span className="text-muted-foreground">&rarr;</span>
                  <span className="font-medium">{returnFlight.destination}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {new Date(returnFlight.departure).toLocaleDateString()} at {new Date(returnFlight.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Return</p>
                <p className="text-lg font-bold text-blue-600">${returnPrice.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">per person</p>
              </div>
            </div>
            {returnSegmentsList.length > 1 && (
              <div className="mt-3 pt-3 border-t border-border space-y-2">
                <p className="text-[10px] uppercase tracking-wide font-medium text-muted-foreground">{returnSegmentsList.length} Segments</p>
                {returnSegmentsList.map((seg, i) => (
                  <div key={seg.id}>
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-medium">{seg.flight_number}</span>
                        <span>{seg.origin}</span>
                        <span className="text-muted-foreground">&rarr;</span>
                        <span>{seg.destination}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{new Date(seg.departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} - {new Date(seg.arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        <span className="font-medium text-foreground">${getClassPrice(seg).toFixed(2)}</span>
                      </div>
                    </div>
                    {i < returnSegmentsList.length - 1 && (() => {
                      const layoverMs = new Date(returnSegmentsList[i + 1].departure).getTime() - new Date(seg.arrival).getTime();
                      const layoverH = Math.floor(layoverMs / 3600000);
                      const layoverM = Math.round((layoverMs % 3600000) / 60000);
                      return (
                        <div className="flex items-center gap-2 py-1 pl-4">
                          <div className="w-3 border-l-2 border-dashed border-muted-foreground/40 h-4" />
                          <span className="text-[10px] text-muted-foreground">Layover in {seg.destination} &middot; {layoverH > 0 ? `${layoverH}h ` : ""}{layoverM}m</span>
                        </div>
                      );
                    })()}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        <div className="flex justify-end items-center gap-3 px-1">
          <span className="text-sm text-muted-foreground">{passengers.length} passenger{passengers.length > 1 ? "s" : ""} &times; ${perPersonPrice.toFixed(2)}</span>
          {discount > 0 && <span className="text-sm text-muted-foreground line-through">${subtotal.toFixed(2)}</span>}
          <span className="text-xl font-bold text-blue-600">${finalPrice.toFixed(2)}</span>
        </div>
      </div>

      {/* Step 1: Passenger Details */}
      {step === "details" && (
        <Card className="p-6 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Passengers ({passengers.length})</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={addPassenger}
              disabled={passengers.length >= (getClassAvailable(flight) || 10)}
            >
              + Add Passenger
            </Button>
          </div>
          <div className="space-y-4">
            {passengers.map((pax, i) => (
              <div key={i} className={`space-y-3 ${i > 0 ? "pt-4 border-t border-border" : ""}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-medium text-muted-foreground">Passenger {i + 1}</p>
                    <div className="flex items-center gap-1">
                      {currentUser && (
                        <button
                          type="button"
                          onClick={() => fillSelf(i)}
                          className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/60 transition-colors font-medium"
                        >
                          Self
                        </button>
                      )}
                      {savedPassengers.length > 0 && (
                        <select
                          className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium border-none outline-none cursor-pointer"
                          value=""
                          onChange={(e) => {
                            const idx = parseInt(e.target.value);
                            if (!isNaN(idx)) fillSavedPassenger(i, savedPassengers[idx]);
                          }}
                        >
                          <option value="" disabled>Saved</option>
                          {savedPassengers.map((sp, si) => (
                            <option key={sp.email} value={si}>{sp.name} ({sp.email})</option>
                          ))}
                        </select>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {pax.name.trim() && pax.email.trim() && !savedPassengers.find(s => s.email.toLowerCase() === pax.email.toLowerCase()) && !(currentUser && pax.email.toLowerCase() === currentUser.email.toLowerCase()) && (
                      <button
                        type="button"
                        onClick={() => savePassengerToList(pax)}
                        className="text-[10px] text-blue-600 hover:underline"
                      >
                        Save for later
                      </button>
                    )}
                    {i > 0 && (
                      <button
                        type="button"
                        onClick={() => removePassenger(i)}
                        className="text-xs text-destructive hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_80px] gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Full Name</label>
                    <Input value={pax.name} onChange={(e) => updatePassenger(i, "name", e.target.value)} placeholder="John Smith" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Email</label>
                    <Input type="email" value={pax.email} onChange={(e) => updatePassenger(i, "email", e.target.value)} placeholder="john@example.com" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Age</label>
                    <Input type="number" min="1" max="120" value={pax.age} onChange={(e) => updatePassenger(i, "age", e.target.value)} placeholder="30" />
                  </div>
                </div>
              </div>
            ))}

            {passengers.length >= 3 && discount === 0 && (
              <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
                <p className="text-xs text-green-700 dark:text-green-400 font-medium">
                  You qualify for a group discount! Apply code <button type="button" onClick={() => { setCoupon(passengers.length >= 10 ? "BULK10" : passengers.length >= 5 ? "BULK5" : "BULK3"); }} className="font-mono font-bold underline">{passengers.length >= 10 ? "BULK10" : passengers.length >= 5 ? "BULK5" : "BULK3"}</button> to save {passengers.length >= 10 ? "25" : passengers.length >= 5 ? "15" : "10"}%.
                </p>
              </div>
            )}

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Contact Phone</label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1-555-0000" />
            </div>

            {/* Promo Code */}
            <div className="pt-3 border-t border-border">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Promo Code (optional)</label>
              <div className="flex gap-2">
                <Input value={coupon} onChange={(e) => setCoupon(e.target.value.toUpperCase())} placeholder="e.g. WELCOME20" className="uppercase" />
                <Button variant="outline" size="sm" onClick={applyCoupon} type="button">Apply</Button>
              </div>
              {couponMsg && (
                <p className={`text-xs mt-1 ${discount > 0 ? "text-green-600" : "text-destructive"}`}>{couponMsg}</p>
              )}

              {availableOffers.length > 0 && discount === 0 && (
                <div className="mt-3 space-y-1.5">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Available Offers</p>
                  {availableOffers.slice(0, 4).map((offer) => (
                    <button
                      key={offer.code}
                      type="button"
                      onClick={() => { setCoupon(offer.code); }}
                      className="w-full flex items-center gap-2 p-2 rounded-md border border-dashed border-border hover:border-blue-300 hover:bg-blue-50/50 dark:hover:bg-blue-950/30 transition-colors text-left"
                    >
                      <span className="shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center text-[10px] font-bold text-green-700 dark:text-green-400">
                        {offer.discount_percent}%
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="text-xs font-medium block truncate">{offer.description}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">{offer.code}</span>
                      </span>
                      {offer.type === "holiday" && (
                        <Badge variant="secondary" className="text-[9px] shrink-0">Limited</Badge>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <Button
              className="w-full mt-4"
              disabled={!allPassengersValid}
              onClick={() => setStep("payment")}
            >
              Continue to Payment
            </Button>
          </div>
        </Card>
      )}

      {/* Step 2: Payment */}
      {step === "payment" && (
        <Card className="p-6 animate-fade-in">
          <h2 className="font-semibold mb-4">Payment Details</h2>
          <div className="space-y-4">

            {/* Points Section */}
            {loyaltyPoints > 0 && (
              <div className="p-4 rounded-lg border-2 border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                    <span className="text-sm font-semibold">Loyalty Points</span>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={usePoints}
                      onChange={(e) => {
                        setUsePoints(e.target.checked);
                        if (e.target.checked) {
                          const maxPoints = Math.min(loyaltyPoints, Math.ceil(afterDiscount / 0.01));
                          setPointsToUse(maxPoints);
                        } else {
                          setPointsToUse(0);
                        }
                      }}
                      className="rounded border-border"
                    />
                    <span className="text-xs font-medium">Use points</span>
                  </label>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-muted-foreground">Available now</p>
                    <p className="font-bold text-lg text-amber-700 dark:text-amber-400">{loyaltyPoints.toLocaleString()}</p>
                    <p className="text-muted-foreground">Worth ${(loyaltyPoints * 0.01).toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Earned (12 months)</p>
                    <p className="font-bold text-lg">{pointsEarned12m.toLocaleString()}</p>
                    <p className="text-muted-foreground">10 pts per $1 spent</p>
                  </div>
                </div>
                {usePoints && (
                  <div className="mt-3 pt-3 border-t border-amber-200 dark:border-amber-800">
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Points to use (max {Math.min(loyaltyPoints, Math.ceil(afterDiscount / 0.01)).toLocaleString()})</label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={pointsToUse}
                        min={0}
                        max={Math.min(loyaltyPoints, Math.ceil(afterDiscount / 0.01))}
                        onChange={(e) => {
                          const val = Math.min(Math.max(0, parseInt(e.target.value) || 0), loyaltyPoints, Math.ceil(afterDiscount / 0.01));
                          setPointsToUse(val);
                        }}
                        className="w-32"
                      />
                      <span className="text-xs text-muted-foreground">= ${(pointsToUse * 0.01).toFixed(2)} off</span>
                      <button
                        type="button"
                        onClick={() => setPointsToUse(Math.min(loyaltyPoints, Math.ceil(afterDiscount / 0.01)))}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Use max
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Card Details (only if remaining balance after points) */}
            {finalPrice > 0 && (
              <>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">Card Number</label>
                  <Input value={cardNumber} onChange={(e) => setCardNumber(e.target.value)} placeholder="4111 1111 1111 1111" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Expiry</label>
                    <Input value={expiry} onChange={(e) => setExpiry(e.target.value)} placeholder="MM/YY" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">CVV</label>
                    <Input value={cvv} onChange={(e) => setCvv(e.target.value)} placeholder="123" type="password" />
                  </div>
                </div>
              </>
            )}

            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex justify-between text-sm">
                <span>{flight.flight_number} ({flight.origin} &rarr; {flight.destination})</span>
                <span>${outboundPrice.toFixed(2)} &times; {passengers.length}</span>
              </div>
              {isRoundTrip && returnFlight && (
                <div className="flex justify-between text-sm">
                  <span>{returnFlight.flight_number} ({returnFlight.origin} &rarr; {returnFlight.destination})</span>
                  <span>${returnPrice.toFixed(2)} &times; {passengers.length}</span>
                </div>
              )}
              <div className="flex justify-between text-sm text-muted-foreground pt-1">
                <span>{passengers.length} passenger{passengers.length > 1 ? "s" : ""}</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              {discount > 0 && (
                <div className="flex justify-between text-sm text-green-600">
                  <span>Discount ({discount}%)</span>
                  <span>-${(subtotal * discount / 100).toFixed(2)}</span>
                </div>
              )}
              {pointsValue > 0 && (
                <div className="flex justify-between text-sm text-amber-600">
                  <span>Points ({pointsToUse.toLocaleString()} pts)</span>
                  <span>-${pointsValue.toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between font-semibold text-sm pt-2 mt-2 border-t border-border">
                <span>{finalPrice <= 0 ? "Total (paid with points)" : "To pay"}</span>
                <span>${finalPrice.toFixed(2)}</span>
              </div>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("details")}>Back</Button>
              <Button
                className="flex-1"
                disabled={(finalPrice > 0 && (!cardNumber.trim() || !expiry.trim() || !cvv.trim())) || submitting}
                onClick={handleBook}
              >
                {submitting ? "Processing..." : finalPrice <= 0 ? "Confirm Booking (Points)" : `Pay $${finalPrice.toFixed(2)}`}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 3: Confirmation */}
      {step === "confirmation" && bookings.length > 0 && (
        <Card className="p-6 animate-fade-in">
          <div className="text-center mb-6">
            <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-bold mb-1">
              {bookings.length > 1 ? `${bookings.length} Bookings Confirmed!` : isRoundTrip ? "Round Trip Confirmed!" : "Booking Confirmed!"}
            </h2>
            <p className="text-sm text-muted-foreground">
              {bookings.length > 1 ? `All ${bookings.length} passengers have been booked.` : isRoundTrip ? "Your flights have been booked successfully." : "Your flight has been booked successfully."}
            </p>
          </div>

          <div className="space-y-3">
            {bookings.map((bk, i) => (
              <div key={bk.id} className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 border border-border">
                <div className="bg-white p-1.5 rounded border border-border/50 shrink-0">
                  <QRCodeSVG value={`https://autopilotairlines.com/bookings/${bk.id}`} size={56} level="M" includeMargin={false} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-sm">{bk.pnr}</span>
                    <Badge variant="secondary" className="text-[9px]">{bk.status}</Badge>
                  </div>
                  <p className="text-sm truncate">{bk.passenger_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {flight.flight_number} · {flight.origin} &rarr; {flight.destination}
                    {isRoundTrip && returnFlight && returnBookings[i] && (
                      <> + {returnFlight.flight_number} · {returnFlight.origin} &rarr; {returnFlight.destination}</>
                    )}
                  </p>
                </div>
                {isRoundTrip && returnBookings[i] && (
                  <div className="text-right shrink-0">
                    <p className="text-[10px] text-muted-foreground">Return PNR</p>
                    <p className="font-mono font-bold text-xs">{returnBookings[i].pnr}</p>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="p-3 rounded-lg bg-muted/50 border border-border text-sm mt-4">
            <div className="grid grid-cols-2 gap-x-6 gap-y-2">
              <span className="text-muted-foreground">Passengers</span>
              <span>{bookings.length}</span>
              <span className="text-muted-foreground">Amount Paid</span>
              <span className="font-semibold">${finalPrice.toFixed(2)}</span>
              {discount > 0 && (
                <>
                  <span className="text-muted-foreground">Discount Applied</span>
                  <span className="text-green-600">{discount}% off</span>
                </>
              )}
            </div>
          </div>

          <p className="text-xs text-muted-foreground mt-4 text-center">
            Confirmation emails have been sent to all passengers.
          </p>

          <div className="flex gap-3 justify-center mt-6 pt-4 border-t border-border">
            <Link href="/bookings">
              <Button variant="outline">View My Bookings</Button>
            </Link>
            <Link href={`/checkin?pnr=${bookings[0].pnr}`}>
              <Button>Check In</Button>
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}
