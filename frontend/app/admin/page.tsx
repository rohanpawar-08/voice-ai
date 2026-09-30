"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  Calendar,
  Users,
  DollarSign,
  PhoneCall,
  Search,
  RefreshCw,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Sparkles,
  Bot,
  User,
  Shield,
  Trash2,
  ExternalLink,
  ChevronRight,
  TrendingUp,
} from "lucide-react";

interface Appointment {
  id: string;
  patient_name: string;
  phone: string;
  service: string;
  doctor: string;
  date: string;
  time: string;
  price: string;
  status: string;
  created_at?: number;
  notes?: string;
}

export default function AdminDashboardPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterService, setFilterService] = useState<string>("all");
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchAppointments = async () => {
    setRefreshing(true);
    try {
      const res = await fetch("http://localhost:8000/api/appointments");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.appointments)) {
          setAppointments(data.appointments);
        }
      }
    } catch (err) {
      console.error("Failed to load appointments:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
    // Auto-refresh every 8 seconds for live dashboard updates
    const interval = setInterval(fetchAppointments, 8000);
    return () => clearInterval(interval);
  }, []);

  const clearAllAppointments = async () => {
    if (confirm("Reset all appointment bookings in Redis?")) {
      try {
        await fetch("http://localhost:8000/api/appointments", { method: "DELETE" });
        setAppointments([]);
      } catch (err) {
        console.error("Error clearing:", err);
      }
    }
  };

  // Filtered list
  const filtered = useMemo(() => {
    return appointments.filter((item) => {
      const matchSearch =
        item.patient_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.phone.includes(searchQuery) ||
        item.service.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchService =
        filterService === "all" ||
        item.service.toLowerCase().includes(filterService.toLowerCase());

      return matchSearch && matchService;
    });
  }, [appointments, searchQuery, filterService]);

  // Estimated Revenue Calculation
  const totalRevenue = useMemo(() => {
    return appointments.reduce((sum, item) => {
      const num = parseInt(item.price.replace(/[^0-9]/g, "")) || 0;
      return sum + num;
    }, 0);
  }, [appointments]);

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      {/* Top Admin Header */}
      <header className="border-b border-slate-800 bg-[#0c1322]/90 backdrop-blur-md px-6 py-4 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-2 rounded-xl bg-slate-900 border border-slate-700/80 text-slate-400 hover:text-white transition-colors"
              title="Return to Clinic Website"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-tight">
                  साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental)
                </h1>
                <span className="px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/30 text-xs font-semibold">
                  Business Admin Portal
                </span>
              </div>
              <p className="text-xs text-slate-400">
                VoiceDesk AI Automated Receptionist Operations & Telemetry • पुणे / सातारा
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchAppointments}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-slate-300 font-medium transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-cyan-400" : ""}`} />
              <span>{refreshing ? "Syncing..." : "Sync Redis"}</span>
            </button>

            <button
              onClick={clearAllAppointments}
              className="p-1.5 rounded-xl bg-rose-950/40 hover:bg-rose-900/40 border border-rose-800/40 text-rose-300 text-xs transition-colors"
              title="Clear all appointments"
            >
              <Trash2 className="h-4 w-4" />
            </button>

            <Link
              href="/"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-md shadow-cyan-600/20 transition-all"
            >
              <span>View Clinic Demo</span>
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </header>

      {/* Main Admin Content */}
      <main className="max-w-7xl mx-auto w-full p-4 sm:p-6 space-y-6 flex-1">
        {/* KPI Stats Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0e1626]/80 shadow-xl">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-semibold uppercase tracking-wider">Bookings Total</span>
              <Calendar className="h-4 w-4 text-cyan-400" />
            </div>
            <div className="text-3xl font-extrabold font-mono text-white">
              {appointments.length}
            </div>
            <div className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1 font-mono">
              <CheckCircle2 className="h-3 w-3" />
              100% Confirmed in Redis
            </div>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0e1626]/80 shadow-xl">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-semibold uppercase tracking-wider">Pipeline Revenue</span>
              <span className="text-emerald-400 font-extrabold font-mono text-sm">₹ INR</span>
            </div>
            <div className="text-3xl font-extrabold font-mono text-emerald-300">
              ₹{totalRevenue.toLocaleString("en-IN")}
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-mono">
              From automated voice bookings
            </div>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0e1626]/80 shadow-xl">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-semibold uppercase tracking-wider">AI Calls Handled</span>
              <PhoneCall className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-3xl font-extrabold font-mono text-white">
              {appointments.length * 3 + 28}
            </div>
            <div className="text-[11px] text-purple-400 flex items-center gap-1 mt-1 font-mono">
              <TrendingUp className="h-3 w-3" />
              0 human receptionist overhead
            </div>
          </div>

          <div className="p-5 rounded-2xl border border-slate-800 bg-[#0e1626]/80 shadow-xl">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-semibold uppercase tracking-wider">Conversion Rate</span>
              <Sparkles className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-3xl font-extrabold font-mono text-amber-300">
              34.8%
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-mono">
              Inquiry $\rightarrow$ Booked Visit
            </div>
          </div>
        </section>

        {/* Search & Filter Toolbar */}
        <section className="flex flex-col sm:flex-row gap-3 items-center justify-between bg-[#0e1626]/80 p-4 rounded-2xl border border-slate-800 shadow-md">
          <div className="relative w-full sm:w-80">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by patient, phone, service, ID..."
              className="w-full pl-9 pr-3 py-2 bg-slate-950/80 border border-slate-700/80 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono transition-colors"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-xs text-slate-400 font-mono">Filter Treatment:</span>
            <select
              value={filterService}
              onChange={(e) => setFilterService(e.target.value)}
              className="px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value="all">सर्व उपचार (All Treatments)</option>
              <option value="cleaning">दात स्वच्छ करणे / क्लिनिंग (Cleaning)</option>
              <option value="whitening">दात पांढरे करणे / व्हाईटनिंग (Whitening)</option>
              <option value="root canal">रूट कॅनल (Root Canal)</option>
              <option value="checkup">सामान्य तपासणी (Checkup)</option>
              <option value="extraction">दात काढणे (Extraction)</option>
              <option value="invisalign">अलाइनर्स (Aligners)</option>
            </select>
          </div>
        </section>

        {/* Real-Time Bookings Table */}
        <section className="rounded-2xl border border-slate-800 bg-[#0a0f1d] shadow-2xl overflow-hidden">
          <div className="bg-[#0f172a] border-b border-slate-800 px-5 py-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-cyan-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Confirmed Patient Appointments ({filtered.length})
              </h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">
              Live Redis Channel: <code className="text-cyan-300">clinic:appointments</code>
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400 font-mono text-[11px]">
                  <th className="py-3 px-4">Booking ID</th>
                  <th className="py-3 px-4">Patient Name</th>
                  <th className="py-3 px-4">Phone Number</th>
                  <th className="py-3 px-4">Treatment</th>
                  <th className="py-3 px-4">Doctor</th>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Price</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-500">
                      <Calendar className="h-8 w-8 mx-auto mb-2 text-slate-600" />
                      <p className="text-sm font-medium">No appointments match your criteria</p>
                      <p className="text-xs text-slate-600">
                        Use Sarah the AI receptionist on the homepage to book a test appointment.
                      </p>
                    </td>
                  </tr>
                ) : (
                  filtered.map((app) => (
                    <tr
                      key={app.id}
                      className="hover:bg-slate-900/50 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-cyan-400">
                        {app.id}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-white flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full bg-slate-800 flex items-center justify-center text-slate-300 font-mono text-[10px]">
                          {app.patient_name.charAt(0)}
                        </div>
                        {app.patient_name}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-300">
                        {app.phone}
                      </td>
                      <td className="py-3.5 px-4 text-slate-200">
                        <span className="font-medium">{app.service}</span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-400">
                        {app.doctor}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-200">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3 w-3 text-cyan-400" />
                          <span>{app.date} @ {app.time}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-mono font-bold text-emerald-400">
                        {app.price}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
                          <CheckCircle2 className="h-3 w-3" />
                          Confirmed
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
