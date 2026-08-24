"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace("/");
    }
  }, [router]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.signup(username, email, password);
      setToken(result.access_token);
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not create the account. Check that the API is running."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <form onSubmit={handleSubmit} className="glass p-8 w-full max-w-sm space-y-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text">
            Create your account
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            Sign up to start screening resumes.
          </p>
        </div>

        <label className="block space-y-1">
          <span className="text-sm text-text-secondary">Username</span>
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text focus:border-accent"
            required
          />
        </label>

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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text focus:border-accent"
            minLength={8}
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm text-text-secondary">Confirm password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-text focus:border-accent"
            minLength={8}
            required
          />
        </label>

        {error && (
          <p className="text-sm text-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="primaryButton w-full" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>

        <p className="text-sm text-text-secondary text-center">
          Already have an account?{" "}
          <Link href="/login" className="text-accent underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
