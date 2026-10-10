"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, Building, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import { API_BASE_URL, setAuthToken, setUserInfo } from "../../../lib/api";

export default function AdminLoginPage() {
  const router = useRouter();
  const [tenantSlug, setTenantSlug] = useState("sai-smile");
  const [identifier, setIdentifier] = useState("admin@saismile.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_slug: tenantSlug.trim(),
          identifier: identifier.trim(),
          password: password,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const errMsg =
          data?.detail ||
          data?.message ||
          "Authentication failed. Please verify your credentials.";
        setError(typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg));
        setLoading(false);
        return;
      }

      const data = await res.json();
      setAuthToken(data.access_token);
      setUserInfo(data.user);

      router.push("/admin");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to reach the authentication server");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center items-center gap-2 mb-2">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <span className="text-xl font-bold tracking-tight text-white">VoiceDesk AI</span>
        </div>
        <h2 className="mt-2 text-center text-2xl font-bold tracking-tight text-white">
          Tenant Staff Login
        </h2>
        <p className="mt-1 text-center text-sm text-slate-400">
          Sign in to access your tenant voice operations and appointments
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-900/80 backdrop-blur-md py-8 px-4 shadow-xl border border-slate-800 sm:rounded-2xl sm:px-10">
          {error && (
            <div className="mb-4 rounded-xl bg-red-950/50 border border-red-800/60 p-3 flex items-start gap-3 text-red-300 text-sm">
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Tenant Slug
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
                  <Building className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="e.g. sai-smile"
                  className="block w-full rounded-lg border border-slate-800 bg-slate-950/60 pl-10 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Email or Phone
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="admin@saismile.com"
                  className="block w-full rounded-lg border border-slate-800 bg-slate-950/60 pl-10 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Password
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full rounded-lg border border-slate-800 bg-slate-950/60 pl-10 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 rounded-lg shadow-sm text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Signing in..." : "Sign in to Dashboard"}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </form>

          <div className="mt-6 border-t border-slate-800/80 pt-4 text-center">
            <p className="text-xs text-slate-500">
              Dev Admin Seed: <code className="text-slate-400">admin@saismile.com</code> /{" "}
              <code className="text-slate-400">Admin@1234</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
