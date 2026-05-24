"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useAuthStore } from "@/lib/store";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { login, register } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const success = isRegister ? await register(email, password, name, dob) : await login(email, password);
    if (success) {
      router.push("/");
    } else {
      setError(isRegister ? "Registration failed" : "Invalid email or password");
    }
    setLoading(false);
  };

  const fillDemo = (demoEmail: string, pass: string) => {
    setEmail(demoEmail);
    setPassword(pass);
    setIsRegister(false);
    setError("");
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center px-4 py-12 bg-gradient-to-b from-blue-50/50 to-transparent dark:from-blue-950/20 dark:to-transparent">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="text-center mb-6">
          <div className="w-12 h-12 mx-auto mb-3 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-600/20">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold">{isRegister ? "Create account" : "Welcome back"}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isRegister ? "Get started with AutoPilot Airlines" : "Sign in to your account"}
          </p>
        </div>

        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Full Name</label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Smith"
                  required
                />
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>
            {isRegister && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Date of Birth</label>
                <Input
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  required
                />
              </div>
            )}
            {error && (
              <p className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
            </Button>
          </form>
          <p className="text-sm text-center mt-4 text-muted-foreground">
            {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-blue-600 hover:underline font-medium"
            >
              {isRegister ? "Sign in" : "Register"}
            </button>
          </p>
        </Card>

        <div className="mt-4 p-4 rounded-xl bg-muted/50 border border-border">
          <p className="text-xs font-medium text-muted-foreground mb-2 text-center">Demo accounts</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => fillDemo("john@example.com", "password123")}
              className="text-xs text-left px-3 py-2 rounded-md bg-background border border-border hover:border-blue-300 transition-colors"
            >
              <span className="font-medium block">Traveler</span>
              <span className="text-muted-foreground">john@example.com</span>
            </button>
            <button
              onClick={() => fillDemo("admin@autopilot.com", "password123")}
              className="text-xs text-left px-3 py-2 rounded-md bg-background border border-border hover:border-blue-300 transition-colors"
            >
              <span className="font-medium block">Admin</span>
              <span className="text-muted-foreground">admin@autopilot.com</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
