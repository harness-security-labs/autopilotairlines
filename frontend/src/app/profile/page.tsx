"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  phone: string | null;
  ssn: string | null;
  credit_card: string | null;
  loyalty_tier: string;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    setIsLoggedIn(true);
    fetch(`${API_URL}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setProfile(data);
          setName(data.name || "");
          setPhone(data.phone || "");
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/v1/users/${profile.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name, phone }),
      });
      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        setEditing(false);
        setSaveMsg("Profile updated successfully");
        setTimeout(() => setSaveMsg(""), 3000);
      } else {
        setSaveMsg("Failed to update profile");
      }
    } catch {
      setSaveMsg("Error saving changes");
    }
    setSaving(false);
  };

  const tierColor = (tier: string) => {
    switch (tier) {
      case "platinum": return "bg-slate-700 text-white";
      case "gold": return "bg-yellow-500 text-white";
      case "silver": return "bg-slate-400 text-white";
      default: return "bg-amber-700 text-white";
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-40 bg-muted rounded" />
          <Card className="p-6"><div className="h-40 bg-muted rounded" /></Card>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-2">Profile</h1>
        <Card className="p-8 text-center">
          <p className="text-muted-foreground mb-4">Sign in to view your profile</p>
          <Link href="/login">
            <Button>Sign In</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Profile</h1>
          <p className="text-sm text-muted-foreground mt-1">Your account details</p>
        </div>
        {!editing && (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            Edit Profile
          </Button>
        )}
      </div>

      {saveMsg && (
        <div className="mb-4 px-3 py-2 rounded-md bg-green-50 text-green-700 text-sm border border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800">
          {saveMsg}
        </div>
      )}

      <Card className="p-6">
        <div className="space-y-5">
          {/* Name */}
          <div className="grid grid-cols-3 gap-4 items-center">
            <label className="text-sm font-medium text-muted-foreground">Name</label>
            <div className="col-span-2">
              {editing ? (
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              ) : (
                <p className="text-sm font-medium">{profile?.name || "---"}</p>
              )}
            </div>
          </div>

          {/* Email */}
          <div className="grid grid-cols-3 gap-4 items-center">
            <label className="text-sm font-medium text-muted-foreground">Email</label>
            <div className="col-span-2">
              <p className="text-sm">{profile?.email}</p>
            </div>
          </div>

          {/* Phone */}
          <div className="grid grid-cols-3 gap-4 items-center">
            <label className="text-sm font-medium text-muted-foreground">Phone</label>
            <div className="col-span-2">
              {editing ? (
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1-555-0000" />
              ) : (
                <p className="text-sm">{profile?.phone || "---"}</p>
              )}
            </div>
          </div>

          {/* Role */}
          <div className="grid grid-cols-3 gap-4 items-center">
            <label className="text-sm font-medium text-muted-foreground">Role</label>
            <div className="col-span-2">
              <Badge variant="secondary" className="capitalize">{profile?.role}</Badge>
            </div>
          </div>

          {/* Loyalty Tier */}
          <div className="grid grid-cols-3 gap-4 items-center">
            <label className="text-sm font-medium text-muted-foreground">Loyalty Tier</label>
            <div className="col-span-2">
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${tierColor(profile?.loyalty_tier || "bronze")}`}>
                {profile?.loyalty_tier || "bronze"}
              </span>
            </div>
          </div>

          <div className="border-t border-border pt-5 mt-5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Payment & Identity</p>

            <div className="grid grid-cols-3 gap-4 items-center mb-4">
              <label className="text-sm font-medium text-muted-foreground">Payment Methods</label>
              <div className="col-span-2">
                <Link href="/payments">
                  <Button variant="outline" size="sm">Manage Payment Methods</Button>
                </Link>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 items-center">
              <label className="text-sm font-medium text-muted-foreground">SSN</label>
              <div className="col-span-2">
                <p className="text-sm font-mono">{profile?.ssn || "---"}</p>
              </div>
            </div>
          </div>

          {/* Edit Actions */}
          {editing && (
            <div className="flex gap-2 pt-4 border-t border-border">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
              <Button variant="outline" onClick={() => { setEditing(false); setName(profile?.name || ""); setPhone(profile?.phone || ""); }}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
