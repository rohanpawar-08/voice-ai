"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  Phone,
  ShieldCheck,
  Clock,
  MapPin,
  Star,
  CheckCircle2,
  Calendar,
  ArrowRight,
  Smile,
  Zap,
  Activity,
  Award,
  ChevronRight,
  ExternalLink,
  Bot,
} from "lucide-react";
import FloatingCallWidget from "@/components/FloatingCallWidget";

export default function ClinicLandingPage() {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  const services = [
    {
      id: "cleaning",
      title: "Dental Cleaning & Hygiene (दात स्वच्छ करणे / क्लिनिंग)",
      price: "₹800",
      duration: "30 mins",
      doctor: "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
      description: "Comprehensive ultrasonic scaling, plaque removal, tartar cleaning, and enamel polishing.",
      popular: true,
    },
    {
      id: "root-canal",
      title: "Root Canal Therapy (रूट कॅनल ट्रीटमेंट)",
      price: "₹3,500",
      duration: "60 mins",
      doctor: "डॉ. राहुल देशमुख (Dr. Rahul Deshmukh)",
      description: "Gentle, painless laser-assisted pulp therapy and root canal restoration under local anesthesia.",
      popular: true,
    },
    {
      id: "whitening",
      title: "Teeth Whitening (दात पांढरे करणे / व्हाईटनिंग)",
      price: "₹2,500",
      duration: "45 mins",
      doctor: "डॉ. स्नेहा पाटील (Dr. Sneha Patil)",
      description: "Advanced in-clinic laser enamel brightening and cosmetic stain removal in one session.",
      popular: true,
    },
    {
      id: "checkup",
      title: "Consultation & Checkup (सामान्य तपासणी)",
      price: "₹300",
      duration: "20 mins",
      doctor: "डॉ. अमित जोशी (Dr. Amit Joshi)",
      description: "Complete oral examination, digital intraoral inspection, and cavity screening roadmap.",
      popular: false,
    },
    {
      id: "extraction",
      title: "Tooth Extraction (दात काढणे)",
      price: "₹1,000",
      duration: "30 mins",
      doctor: "डॉ. राहुल देशमुख (Dr. Rahul Deshmukh)",
      description: "Safe, painless single or wisdom tooth extraction under modern gentle local anesthesia.",
      popular: false,
    },
    {
      id: "invisalign",
      title: "Clear Aligners Consultation (इनव्हिसिलाइन सल्ला)",
      price: "मोफत (Free Consult)",
      duration: "25 mins",
      doctor: "डॉ. अमित जोशी (Dr. Amit Joshi)",
      description: "Full 3D intraoral digital smile scan and custom aligner simulation at zero cost.",
      popular: false,
    },
  ];

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans selection:bg-teal-500/30">
      {/* Top Clinic Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-[#0c1322]/85 backdrop-blur-md px-6 py-4 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-tr from-teal-500 via-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
              <Smile className="h-6 w-6" />
            </div>
            <div>
              <span className="text-base font-extrabold text-white tracking-tight flex items-center gap-1.5">
                साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic)
                <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
              </span>
              <p className="text-[11px] text-slate-400 font-medium">
                इम्प्लांट व ऑर्थोडॉन्टिक्स सेंटर • शिवाजी नगर, पुणे / सातारा, महाराष्ट्र
              </p>
            </div>
          </div>

          {/* Navigation Links & Admin Portal Button */}
          <div className="flex items-center gap-4">
            <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-slate-300">
              <a href="#services" className="hover:text-cyan-400 transition-colors">
                उपचार व फी (Treatments)
              </a>
              <a href="#doctors" className="hover:text-cyan-400 transition-colors">
                तज्ज्ञ डॉक्टर (Specialists)
              </a>
              <a href="#contact" className="hover:text-cyan-400 transition-colors">
                वेळ व पत्ता (Location)
              </a>
            </nav>

            {/* Link to Admin Dashboard */}
            <Link
              href="/admin"
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/80 text-xs font-semibold text-slate-300 hover:text-white transition-all shadow-sm"
              title="Open Clinic Business Admin Dashboard"
            >
              <Activity className="h-3.5 w-3.5 text-cyan-400" />
              <span>Admin Portal</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-20 px-6 border-b border-slate-800/60 bg-gradient-to-b from-[#0c1322] via-[#080d19] to-[#070b14]">
        {/* Glow backdrop */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-5xl mx-auto text-center space-y-6 relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-xs font-semibold text-cyan-300">
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
            <span>२४/७ मराठी व इंग्रजी AI Voice रिसेप्शनिस्ट व ऑनलाइन बुकिंग</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white tracking-tight leading-tight">
            साई स्माईल डेंटल क्लिनिक.{" "}
            <span className="bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-500 bg-clip-text text-transparent">
              वेदनामुक्त उपचार. सुंदर हास्य.
            </span>
          </h1>

          <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed">
            शिवाजी नगर, पुणे आणि सातारा येथील नामांकित डेंटल क्लिनिक. अत्याधुनिक लेझर दात तपासणी,
            रूट कॅनल व कॉस्मेटिक स्माईल मेकओव्हर. आमची २४/७ AI रिसेप्शनिस्ट <strong>सारा (Sarah)</strong> फोनवर
            मराठी व इंग्रजीमध्ये आपल्या प्रश्नांची उत्तरे देण्यास आणि अपॉइंटमेंट बुक करण्यास सज्ज आहे.
          </p>

          {/* Social Proof Stats */}
          <div className="flex flex-wrap items-center justify-center gap-6 pt-4 text-xs text-slate-400 font-mono">
            <div className="flex items-center gap-1.5">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <span className="font-bold text-white">4.9 / 5</span> (1,250+ रुग्ण पुनरावलोकने)
            </div>
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-teal-400" />
              <span>१००% सुरक्षित व वेदनामुक्त तंत्रज्ञान</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-cyan-400" />
              <span>तातडीच्या वेळेसाठी राखीव स्लॉट्स</span>
            </div>
          </div>
        </div>
      </section>

      {/* AI Voice Assistant Showcase Banner */}
      <section className="px-6 py-8 bg-[#090f1d] border-b border-slate-800">
        <div className="max-w-7xl mx-auto rounded-3xl bg-gradient-to-r from-teal-950/40 via-cyan-950/30 to-blue-950/40 border border-cyan-500/30 p-6 sm:p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-2xl">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-teal-500 to-cyan-500 flex items-center justify-center text-white shadow-xl shadow-cyan-500/30">
                <Bot className="h-8 w-8" />
              </div>
              <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500" />
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white">साराशी बोला — आपली २४/७ AI डेंटल रिसेप्शनिस्ट (Sarah)</h3>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-mono font-bold">
                  मराठी / English Live
                </span>
              </div>
              <p className="text-xs text-slate-300 max-w-xl mt-1">
                दात क्लिनिंग, रूट कॅनल, डॉक्टरांची उपलब्धता किंवा अपॉइंटमेंट बुकिंगसाठी थेट मराठीत बोला.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <p className="text-xs text-cyan-300 font-mono hidden lg:block">
              खालील फोन आयकॉनवर क्लिक करा ↘
            </p>
          </div>
        </div>
      </section>

      {/* Treatments & Pricing Grid */}
      <section id="services" className="px-6 py-16 max-w-7xl mx-auto w-full space-y-10">
        <div className="text-center space-y-2">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            दंत उपचार व पारदर्शक दर (Treatments & Pricing in ₹ INR)
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-lg mx-auto">
            कोणतीही लपलेली फी नाही. थेट साराला व्हॉईसवर विचारून उपचारांची माहिती व वेळ जाणून घ्या.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((svc) => (
            <div
              key={svc.id}
              className="group relative p-6 rounded-2xl border border-slate-800 bg-[#0c1322]/90 hover:border-cyan-500/50 hover:bg-[#0e172a] transition-all duration-300 shadow-xl flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono font-bold text-cyan-400">
                    {svc.duration}
                  </span>
                  {svc.popular && (
                    <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-[10px] font-bold">
                      लोकप्रिय (Popular)
                    </span>
                  )}
                </div>

                <h3 className="text-base font-bold text-white mb-1 group-hover:text-cyan-300 transition-colors">
                  {svc.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed mb-4">
                  {svc.description}
                </p>

                <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5 mb-4">
                  <Award className="h-3.5 w-3.5 text-teal-400" />
                  <span>तज्ज्ञ: {svc.doctor}</span>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase font-mono block">किंमत (Starting at)</span>
                  <span className="text-xl font-extrabold font-mono text-emerald-400">{svc.price}</span>
                </div>

                <div className="text-xs text-cyan-400 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-semibold">
                  <span>साराला सांगा</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Specialists Section */}
      <section id="doctors" className="px-6 py-16 bg-[#080d19] border-t border-b border-slate-800">
        <div className="max-w-7xl mx-auto space-y-10">
          <div className="text-center space-y-2">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              आमचे अनुभवी दंत तज्ज्ञ डॉक्टर (Our Specialists)
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 max-w-lg mx-auto">
              पुणे व सातारा येथील १५+ वर्षांहून अधिक अनुभव असलेले निष्णात दंतवैद्य.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl border border-slate-800 bg-[#0c1322] space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-teal-500/20 text-teal-300 flex items-center justify-center font-bold text-lg">
                SP
              </div>
              <h3 className="text-base font-bold text-white">डॉ. स्नेहा पाटील (Dr. Sneha Patil, MDS)</h3>
              <p className="text-xs text-cyan-400 font-mono">कॉस्मेटिक डेंटिस्ट्री व ओरल हायजिन</p>
              <p className="text-xs text-slate-400 leading-relaxed">
                दात क्लिनिंग, लेझर व्हाइटनिंग, स्माईल डिझायनिंग व मुलांच्या दंत उपचारांमध्ये विशेष प्रावीण्य.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800 bg-[#0c1322] space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold text-lg">
                RD
              </div>
              <h3 className="text-base font-bold text-white">डॉ. राहुल देशमुख (Dr. Rahul Deshmukh, MDS)</h3>
              <p className="text-xs text-purple-400 font-mono">रूट कॅनल व ओरल सर्जरी तज्ज्ञ</p>
              <p className="text-xs text-slate-400 leading-relaxed">
                एकाच बैठकीत आधुनिक मायक्रोस्कोपिक रूट कॅनल, अक्कलदाढ शस्त्रक्रिया व सुरक्षित दात काढणे.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-slate-800 bg-[#0c1322] space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-amber-500/20 text-amber-300 flex items-center justify-center font-bold text-lg">
                AJ
              </div>
              <h3 className="text-base font-bold text-white">डॉ. अमित जोशी (Dr. Amit Joshi, BDS, Implantologist)</h3>
              <p className="text-xs text-amber-400 font-mono">इम्प्लांट्स व ऑर्थोडॉन्टिक्स (Aligners)</p>
              <p className="text-xs text-slate-400 leading-relaxed">
                कमी खर्चात कायमस्वरूपी दात बसवणे (इम्प्लांट्स), इनव्हिसिलाइन क्लिअर अलाइनर्स व डिजिटल तपासणी.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Clinic Location & Hours Section */}
      <section id="contact" className="px-6 py-16 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 p-8 rounded-3xl border border-slate-800 bg-[#0c1322]">
          <div className="space-y-4">
            <h3 className="text-xl font-bold text-white">साई स्माईल क्लिनिक पत्ता व वेळ</h3>
            <div className="space-y-3 text-xs text-slate-300">
              <div className="flex items-start gap-2.5">
                <MapPin className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white block">क्लिनिक पत्ता (Clinic Location):</strong>
                  प्लॉट क्र. १२, मॉडर्न कॉलेज रोड, शिवाजी नगर, पुणे – ४११००५ / शाखा: सातारा, महाराष्ट्र
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <Clock className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white block">वेळ (Timings):</strong>
                  सोमवार – शनिवार: सकाळी ९:०० ते रात्री ८:३० <br />
                  रविवार: सकाळी १०:०० ते दुपारी २:०० (२४/७ इमर्जन्सी कॉलिंग उपलब्ध)
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <Phone className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white block">हेल्पलाइन व बुकिंग:</strong>
                  +91 98220 SAI-DENTAL (AI रिसेप्शनिस्ट सारा २४/७ उपलब्ध)
                </div>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex flex-col justify-between space-y-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 font-mono">
                २४/७ रिअल-टाइम व्हॉईस असिस्टंट
              </span>
              <h4 className="text-base font-bold text-white mt-1">अपॉइंटमेंट बुक करायची आहे?</h4>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                स्क्रीनच्या उजव्या कोपऱ्यातील फोन आयकॉनवर क्लिक करा आणि थेट साराशी मराठी किंवा इंग्रजीमध्ये बोला.
                ती आपले प्रश्न समजून घेऊन लगेच सिस्टीममध्ये आपली वेळ आरक्षित करेल.
              </p>
            </div>

            <div className="pt-2">
              <Link
                href="/admin"
                className="inline-flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 font-semibold"
              >
                <span>क्लिनिक स्टाफ: ॲडमिन पोर्टल उघडा (Admin Portal)</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-[#070b14] py-8 px-6 text-center text-xs text-slate-500 font-mono">
        <p>© 2026 साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic). Powered by VoiceDesk AI.</p>
        <p className="mt-1 text-[11px] text-slate-600">
          FastAPI • LangGraph • Redis • Groq Whisper • Marathi Neural Voice (mr-IN-AarohiNeural)
        </p>
      </footer>

      {/* Floating AI Receptionist Call Widget */}
      <FloatingCallWidget wsUrl="ws://localhost:8000" />
    </div>
  );
}
