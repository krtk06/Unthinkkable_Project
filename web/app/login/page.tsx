"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";
import { RainbowButton } from "@/components/ui/rainbow-button";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace("/");
    }
  }, [router]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(email, password);
      setToken(result.access_token);
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not sign in. Check that the API is running."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#080a0c] text-zinc-200 relative">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.35]"
        aria-hidden="true"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.09) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />
      <div className="relative grid min-h-screen grid-cols-1 lg:grid-cols-2">
        {/* Left half */}
        <div className="flex min-h-[40vh] flex-col items-center justify-center border-b border-white/[0.07] p-8 text-center lg:min-h-screen lg:border-b-0 lg:border-r lg:p-12">
          <div className="space-y-3">
            <p className="font-data text-sm tracking-[0.2em] text-zinc-500">WELCOME</p>
            <h1 className="font-scoria text-5xl font-normal tracking-wide text-white lg:text-6xl">Hirelytics</h1>
          </div>
        </div>

        {/* Right half - form */}
        <div className="flex items-center justify-center p-6 lg:p-12">
          <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-5">
            <div className="space-y-1">
              <h2 className="text-xl font-semibold tracking-tight text-text">Welcome back</h2>
              <p className="text-sm text-text-secondary">Sign in to continue screening candidates.</p>
            </div>

            <label className="block space-y-1">
              <span className="text-sm text-text-secondary">Email</span>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text focus:border-accent"
                required
              />
            </label>

            <label className="block space-y-1">
              <span className="text-sm text-text-secondary">Password</span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text focus:border-accent"
                required
              />
            </label>

            {error && (
              <p className="text-sm text-error" role="alert">
                {error}
              </p>
            )}

            <RainbowButton type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Login"}
            </RainbowButton>

            <p className="text-sm text-text-secondary text-center">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="text-accent underline">
                Create an account
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
