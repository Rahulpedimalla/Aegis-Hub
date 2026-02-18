import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, Activity, Map, Users, ArrowRight, CheckCircle } from 'lucide-react';

const Home = () => {
  const roleCards = [
    {
      role: 'Admin',
      access: 'Full access: dashboards, assignments, organizations, staff, divisions, resources',
      creds: 'admin / admin123',
    },
    {
      role: 'Responder',
      access: 'Operational access: tickets, emergency response, map, resources',
      creds: 'responder, harish.rao, dr.sneha.reddy, kiran.kumar, madhavi.ch / responder123',
    },
    {
      role: 'Viewer',
      access: 'Read-only access: dashboards, map and incident monitoring',
      creds: 'viewer / viewer123',
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(56,189,248,0.18),transparent_45%),radial-gradient(circle_at_bottom_left,_rgba(34,197,94,0.16),transparent_40%)] pointer-events-none" />
      <div className="relative max-w-6xl mx-auto px-6 py-16">
        <header className="flex items-center justify-between mb-16">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-cyan-500/20 border border-cyan-400/30 flex items-center justify-center">
              <Shield className="w-6 h-6 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">AegisHub Telangana</h1>
              <p className="text-xs text-slate-400">AI Disaster Co-ordination Platform</p>
            </div>
          </div>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 text-slate-950 font-semibold hover:bg-cyan-400 transition-colors"
          >
            Login
            <ArrowRight className="w-4 h-4" />
          </Link>
        </header>

        <section className="grid lg:grid-cols-2 gap-10 items-center mb-16">
          <div>
            <p className="text-cyan-300 font-medium mb-3">Real-Time Incident Response</p>
            <h2 className="text-4xl font-bold leading-tight mb-4">
              Smart AI ticket assignment for the right division and response team.
            </h2>
            <p className="text-slate-300 mb-8">
              End-to-end command center for SOS intake, geospatial monitoring, role-based operations and auditable resolution workflow.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-cyan-500 text-slate-950 font-semibold hover:bg-cyan-400 transition-colors"
              >
                Open Dashboard
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="#about"
                className="inline-flex items-center gap-2 px-5 py-3 rounded-lg border border-slate-700 text-slate-100 hover:bg-slate-900 transition-colors"
              >
                About Platform
              </a>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
              <Activity className="w-5 h-5 text-emerald-300 mb-2" />
              <p className="text-sm text-slate-300">AI triage + priority scoring</p>
            </div>
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
              <Users className="w-5 h-5 text-cyan-300 mb-2" />
              <p className="text-sm text-slate-300">Division-aware team assignment</p>
            </div>
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
              <Map className="w-5 h-5 text-amber-300 mb-2" />
              <p className="text-sm text-slate-300">Live map and satellite layers</p>
            </div>
            <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4">
              <Shield className="w-5 h-5 text-violet-300 mb-2" />
              <p className="text-sm text-slate-300">Role-based secure operations</p>
            </div>
          </div>
        </section>

        <section id="about" className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 mb-10">
          <h3 className="text-xl font-semibold mb-4">About</h3>
          <p className="text-slate-300 mb-6">
            AegisHub routes each incident to the most suitable division using AI classification, location, skills and capacity.
            It tracks assignment windows, acceptance, completion and workload updates across organizations, divisions and responders.
          </p>
          <div className="grid md:grid-cols-3 gap-4">
            {roleCards.map((item) => (
              <div key={item.role} className="bg-slate-950/70 border border-slate-800 rounded-xl p-4">
                <p className="font-semibold mb-2">{item.role}</p>
                <p className="text-sm text-slate-300 mb-3">{item.access}</p>
                <p className="text-xs text-cyan-300">{item.creds}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 flex items-center gap-2 text-emerald-300 text-sm">
            <CheckCircle className="w-4 h-4" />
            Demo credentials are enabled for immediate testing.
          </div>
        </section>
      </div>
    </div>
  );
};

export default Home;
