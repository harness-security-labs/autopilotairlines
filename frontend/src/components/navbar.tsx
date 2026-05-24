"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/store";

export function Navbar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const loadToken = useAuthStore((s) => s.loadToken);

  useEffect(() => {
    loadToken();
  }, [loadToken]);

  const isAdmin = user?.role === "admin";

  const navItems = [
    { href: "/", label: "Flights" },
    { href: "/offers", label: "Offers" },
    { href: "/chat", label: "AI Assistant" },
    { href: "/bookings", label: "Bookings" },
    { href: "/checkin", label: "Check-in" },
    { href: "/loyalty", label: "Rewards" },
  ];

  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 dark:bg-slate-900/95 dark:supports-[backdrop-filter]:bg-slate-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14 items-center">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                </svg>
              </div>
              <span className="font-semibold text-foreground">AutoPilot Airlines</span>
            </Link>
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => (
                <Link key={item.href} href={item.href}>
                  <Button
                    variant={pathname === item.href ? "default" : "ghost"}
                    size="sm"
                  >
                    {item.label}
                  </Button>
                </Link>
              ))}
              {isAdmin && (
                <Link href="/admin">
                  <Button
                    variant={pathname === "/admin" ? "default" : "ghost"}
                    size="sm"
                  >
                    Admin
                  </Button>
                </Link>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <>
                <Link href="/profile" className="hidden sm:flex items-center gap-2 hover:opacity-80 transition-opacity">
                  <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-[10px] font-semibold text-white">
                    {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-muted-foreground">{user.email}</span>
                </Link>
                <Button variant="outline" size="sm" onClick={logout}>
                  Sign Out
                </Button>
              </>
            ) : (
              <Link href="/login">
                <Button size="sm">Sign In</Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
