import { useState, useEffect, useRef } from 'react';

// ─── Constants ──────────────────────────────────────────────────────────────────

const ALL_FEATURES = [
  { title: 'WPS SIF File Generation',          desc: 'Generate MOHRE-compliant Salary Information Files in seconds. Supports all UAE banks with CRLF-correct encoding.' },
  { title: 'Employee Management',              desc: 'Full employee records with MOL ID, IBAN, Emirates ID, visa tracking, probation management, and contract lifecycle.' },
  { title: 'Clinical Credential Tracking',     desc: 'DHA, DOH, and MOH licence management with 90/30/14-day expiry alerts. BLS, ACLS, PALS, and NRP certification registry.' },
  { title: 'Leave Management',                 desc: 'Federal Labour Law No. 33 of 2021 compliant leave types, multi-level approval chains, and a visual team leave calendar.' },
  { title: 'Attendance & Biometric Import',     desc: 'Clock-in/out via employee portal, attendance period management, and biometric device CSV import for automated time tracking.' },
  { title: 'Payroll Processing',               desc: 'Full payroll editor with allowances, deductions, salary advance integration, maker-checker approval, and payslip PDF export.' },
  { title: 'Shift Roster & Scheduling',        desc: 'Clinical rota with shift templates, drag-and-drop monthly scheduling, staffing rule compliance, and shift swap requests.' },
  { title: 'Department & Staffing Rules',      desc: 'Department hierarchy with minimum staffing requirements per shift. Publish gate warns when clinical coverage falls short.' },
  { title: 'Salary Advances',                  desc: 'Admin-issued and employee-requested advances with monthly repayment schedules and automatic payroll deduction.' },
  { title: 'Expense Claims',                   desc: 'Employee expense submission with receipt upload, manager and HR approval workflow, and one-click payroll integration.' },
  { title: 'Emiratization / Nafis',            desc: 'Track UAE national headcount against your sector quota with 2026 tiered rules. Generate compliance snapshots with CSV export.' },
  { title: 'Document Storage',                 desc: 'Secure vault for visas, passports, Emirates IDs, and clinical licences with time-limited signed URLs and expiry alerts.' },
  { title: 'Insurance Management',             desc: 'Company insurance policies, employee coverage assignments, family dependants, and renewal tracking.' },
  { title: 'HR Reports & Analytics',           desc: 'Twelve report types including headcount, payroll cost, leave usage, attendance, document expiry, EOS liability, and WPS compliance.' },
  { title: 'Probation Management',             desc: 'Confirm, extend, or terminate probation periods with UAE 14-day notice compliance and dashboard alerts.' },
  { title: 'Contract Renewal Tracking',        desc: 'Automated 60-day alerts for limited contracts. Renew, convert to unlimited, or mark as not renewing.' },
  { title: 'Offboarding Workflows',            desc: 'Clearance checklists, visa cancellation tracking, end-of-service gratuity calculation, and NOC and experience letter printing.' },
  { title: 'Training & CME Tracking',          desc: 'Training records and certification registry with CME hour tracking. Self-service submission with admin verification workflow.' },
  { title: 'Appraisal Management',             desc: 'Appraisal cycles with section-based review forms, manager star ratings, HR calibration, and multi-portal visibility.' },
  { title: 'Letter Requests',                  desc: 'Seven HR letter templates — salary certificate, NOC, experience letter, and more — with employee self-service requests.' },
  { title: 'Multi-Company Support',            desc: 'Manage multiple clinic branches from one login. Switch context in the sidebar with full data isolation per branch.' },
  { title: 'Three-Portal Architecture',        desc: 'Dedicated portals for HR administrators, line managers, and employees — each with role-appropriate views and permissions.' },
  { title: 'Smart Notifications',              desc: 'In-app alerts for document expiries, leave decisions, payslip availability, payroll approval, and clinical credential renewals.' },
  { title: 'Asset Management',                 desc: 'Company asset registry with assignment history, condition tracking, and employee self-view of assigned assets.' },
];

const STARTER_FEATURES = [
  'Up to 10 employees',
  'WPS SIF file generation',
  'Employee management',
  'Leave management — UAE compliant',
  'Attendance tracking',
  'Employee self-service portal',
  'Payslip PDF generation',
  'Email support',
];

const GROWTH_FEATURES = [
  'Up to 50 employees',
  'Everything in Starter',
  'Clinical credential tracking',
  'Payroll approval workflow',
  'Document storage — 1 GB',
  'Insurance management',
  'Salary advances & expense claims',
  'Shift roster & staffing rules',
  'Training & CME hour tracking',
  'Appraisal management',
  'HR reports & analytics (12 types)',
  'Emiratization / Nafis compliance',
  'Contract & offboarding workflows',
  'Multi-company branch support',
  'Manager portal',
  'Priority support',
];

// ─── Main component ─────────────────────────────────────────────────────────

export default function LandingPage({ onSignIn, onGetStarted }) {
  // 'home' | 'features' | 'pricing' | 'about'
  const [page, setPage]         = useState('home');
  const [scrolled, setScrolled] = useState(false);
  const [pageTransition, setPageTransition] = useState('idle');
  const transitionTimerRef = useRef(null);
  const pendingPageRef = useRef('home');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => () => clearTimeout(transitionTimerRef.current), []);

  const navigateToPage = nextPage => {
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (nextPage === page && pageTransition === 'idle') {
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
      return;
    }

    pendingPageRef.current = nextPage;
    clearTimeout(transitionTimerRef.current);

    if (reduceMotion) {
      setPage(nextPage);
      setPageTransition('idle');
      window.scrollTo({ top: 0, behavior: 'auto' });
      return;
    }

    setPageTransition('leaving');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    transitionTimerRef.current = setTimeout(() => {
      setPage(pendingPageRef.current);
      setPageTransition('entering');
      transitionTimerRef.current = setTimeout(() => setPageTransition('idle'), 420);
    }, 180);
  };

  // ── Nav ───────────────────────────────────────────────────────────────────

  function renderNav() {
    const onHero = page === 'home' && !scrolled;

    const navBg = onHero
      ? 'rgba(0,0,0,0.20)'
      : 'rgba(255,255,255,0.82)';
    const navBorder = onHero
      ? 'none'
      : '1px solid rgba(0,0,0,0.08)';
    const logoColor = onHero ? '#fff' : '#1d1d1f';

    return (
      <nav style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200, height: 56,
        background: navBg, backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
        borderBottom: navBorder,
        display: 'flex', alignItems: 'center', padding: '0 40px',
        overflow: 'hidden',
        transition: 'background 0.3s, border 0.3s',
      }}>
        <button onClick={() => navigateToPage('home')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px', color: logoColor, padding: 0, marginRight: 36 }}>
          Workloop
        </button>

        <div style={{ display: 'flex', gap: 0, flex: 1 }}>
          {['home', 'features', 'pricing', 'about'].map(p => (
            <button key={p} onClick={() => navigateToPage(p)} className={`landing-nav-link ${page === p ? 'active' : ''}`} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 14, fontWeight: 400, padding: '0 16px',
              color: onHero
                ? page === p ? '#fff' : 'rgba(255,255,255,0.72)'
                : page === p ? '#1d1d1f' : '#6e6e73',
              transition: 'color 0.15s',
            }}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button onClick={onSignIn} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, padding: '6px 12px', borderRadius: 8, color: onHero ? 'rgba(255,255,255,0.80)' : '#6e6e73', fontWeight: 500 }}>
            Sign in
          </button>
          <button onClick={onGetStarted} style={{ background: '#0071e3', border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500, padding: '8px 20px', borderRadius: 980, color: '#fff' }}>
            Get started
          </button>
        </div>
      </nav>
    );
  }

  // ── Home page ─────────────────────────────────────────────────────────────

  function renderHome() {
    return (
      <>
        {/* Hero — abstract flowing lines on brand navy */}
        <section style={{
          height: '100vh', minHeight: 600,
          background: '#08122e',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', padding: '0 24px',
          position: 'relative', overflow: 'hidden',
        }}>
          {/* Abstract flowing ribbon lines */}
          <svg
            viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.55 }}
          >
            <defs>
              <linearGradient id="ribbonA" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#2563EB" stopOpacity="0" />
                <stop offset="45%" stopColor="#2563EB" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#06B6D4" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="ribbonB" x1="100%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#06B6D4" stopOpacity="0" />
                <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.7" />
                <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="ribbonC" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#818cf8" stopOpacity="0" />
                <stop offset="50%" stopColor="#6366f1" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#06B6D4" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d="M -100,650 C 250,550 450,750 720,600 C 990,450 1150,550 1540,350"
              fill="none" stroke="url(#ribbonA)" strokeWidth="2" strokeLinecap="round"
              style={{ animation: 'ribbonDrift1 22s ease-in-out infinite' }} />
            <path d="M -100,300 C 300,420 500,220 780,340 C 1060,460 1200,300 1540,420"
              fill="none" stroke="url(#ribbonB)" strokeWidth="1.5" strokeLinecap="round"
              style={{ animation: 'ribbonDrift2 26s ease-in-out infinite' }} />
            <path d="M -100,500 C 280,480 520,600 760,480 C 1000,360 1220,480 1540,460"
              fill="none" stroke="url(#ribbonC)" strokeWidth="1.5" strokeLinecap="round"
              style={{ animation: 'ribbonDrift3 30s ease-in-out infinite' }} />
          </svg>
          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{
              display: 'inline-block', padding: '6px 16px', borderRadius: 980,
              background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.10)',
              fontSize: 13, fontWeight: 500, color: 'rgba(255,255,255,0.80)',
              marginBottom: 28, letterSpacing: '0.01em',
            }}>
              Built for UAE clinics & hospitals
            </div>
            <h1 style={{ fontSize: 'clamp(40px, 7vw, 80px)', fontWeight: 700, color: '#f5f5f7', lineHeight: 1.05, letterSpacing: '-0.03em', marginBottom: 20, maxWidth: 820, margin: '0 auto 20px' }}>
              HR and payroll<br />for healthcare.
            </h1>
            <p style={{ fontSize: 19, color: 'rgba(255,255,255,0.55)', maxWidth: 520, marginBottom: 40, lineHeight: 1.65, fontWeight: 400, margin: '0 auto 40px' }}>
              WPS SIF files, clinical credential tracking, shift rostering, and full UAE labour law compliance — without the setup call.
            </p>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 32 }}>
              <button onClick={onGetStarted} style={{ background: '#fff', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 600, padding: '14px 32px', borderRadius: 980, color: '#06101f' }}>
                Get started free
              </button>
              <button onClick={() => navigateToPage('features')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 400, color: '#60a5fa', padding: '14px 4px' }}>
                See all features ›
              </button>
            </div>
          </div>
        </section>

        {/* Tagline */}
        <section style={{ padding: '100px 24px', background: '#fff', textAlign: 'center' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>Built for the UAE</p>
          <h2 style={{ fontSize: 'clamp(28px, 5vw, 52px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.08, letterSpacing: '-0.02em', maxWidth: 780, margin: '0 auto' }}>
            From SIF file to payslip.<br />In minutes, not days.
          </h2>
          <p style={{ fontSize: 19, color: '#6e6e73', maxWidth: 560, margin: '24px auto 0', lineHeight: 1.6 }}>
            No demo call. No implementation project. Set up your clinic's entire HR system yourself — payroll, credentials, rosters, and compliance.
          </p>
        </section>

        {/* Dashboard — image left, text right */}
        <section style={{ background: '#f5f5f7', padding: '100px 80px' }}>
          <div style={{ maxWidth: 1400, margin: '0 auto', display: 'grid', gridTemplateColumns: '5fr 2fr', gap: 48, alignItems: 'center' }}>
            <div style={{
              borderRadius: 16, overflow: 'hidden',
              background: '#0a1628',
              boxShadow: '0 24px 64px rgba(0,0,0,0.15)',
            }}>
              <img src="/images/dashboard.png" alt="Workloop admin dashboard showing headcount, payroll, and compliance" style={{ width: '100%', display: 'block' }} />
            </div>
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>Dashboard</p>
              <h2 style={{ fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 16 }}>Everything in one view.</h2>
              <p style={{ fontSize: 16, color: '#6e6e73', lineHeight: 1.65, marginBottom: 28 }}>
                Headcount, payroll status, leave approvals, expiring clinical licences, and Emiratization quota — visible the moment you log in.
              </p>
              <button onClick={onGetStarted} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#0071e3', padding: 0, fontWeight: 500 }}>
                Get started ›
              </button>
            </div>
          </div>
        </section>

        {/* WPS / SIF — text left, image right */}
        <section style={{ background: '#fff', padding: '100px 80px' }}>
          <div style={{ maxWidth: 1400, margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 5fr', gap: 48, alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>WPS SIF</p>
              <h2 style={{ fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 16 }}>Your SIF file, ready in seconds.</h2>
              <p style={{ fontSize: 16, color: '#6e6e73', lineHeight: 1.65, marginBottom: 28 }}>
                MOHRE-compliant Salary Information Files generated with correct CRLF line endings and integer AED amounts — the format every UAE bank accepts, every time.
              </p>
              <button onClick={onGetStarted} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#0071e3', padding: 0, fontWeight: 500 }}>
                Get started ›
              </button>
            </div>
            <div style={{
              borderRadius: 16, overflow: 'hidden',
              background: '#06102a',
              boxShadow: '0 24px 64px rgba(0,0,0,0.10)',
            }}>
              <img src="/images/payroll.png" alt="Payroll editor with employee salary breakdowns" style={{ width: '100%', display: 'block' }} />
            </div>
          </div>
        </section>

        {/* Clinical credentials — image left, text right */}
        <section style={{ background: '#f5f5f7', padding: '100px 80px' }}>
          <div style={{ maxWidth: 1400, margin: '0 auto', display: 'grid', gridTemplateColumns: '5fr 2fr', gap: 48, alignItems: 'center' }}>
            <div style={{
              borderRadius: 16, overflow: 'hidden',
              background: '#06102a',
              boxShadow: '0 24px 64px rgba(0,0,0,0.10)',
            }}>
              <img src="/images/credentials.png" alt="Clinical credential tracking with DHA and DOH licence expiry alerts" style={{ width: '100%', display: 'block' }} />
            </div>
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>Clinical</p>
              <h2 style={{ fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 16 }}>Never miss a licence renewal.</h2>
              <p style={{ fontSize: 16, color: '#6e6e73', lineHeight: 1.65, marginBottom: 28 }}>
                Track DHA, DOH, and MOH licences with 90, 30, and 14-day expiry alerts. BLS, ACLS, PALS, and NRP certifications with CME hour tracking — built for every clinical role.
              </p>
              <button onClick={() => navigateToPage('features')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#0071e3', padding: 0, fontWeight: 500 }}>
                See all features ›
              </button>
            </div>
          </div>
        </section>

        {/* Roster — text left, image right */}
        <section style={{ background: '#fff', padding: '100px 80px' }}>
          <div style={{ maxWidth: 1400, margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 5fr', gap: 48, alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>Scheduling</p>
              <h2 style={{ fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 16 }}>Clinical rotas, built right.</h2>
              <p style={{ fontSize: 16, color: '#6e6e73', lineHeight: 1.65, marginBottom: 28 }}>
                Shift templates, monthly rostering, staffing rule compliance, leave conflict detection, and employee shift swap requests — all in one screen.
              </p>
              <button onClick={onGetStarted} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#0071e3', padding: 0, fontWeight: 500 }}>
                Get started ›
              </button>
            </div>
            <div style={{
              borderRadius: 16, overflow: 'hidden',
              background: '#0a1628',
              boxShadow: '0 24px 64px rgba(0,0,0,0.10)',
            }}>
              <img src="/images/roster.png" alt="Monthly shift roster with clinical scheduling" style={{ width: '100%', display: 'block' }} />
            </div>
          </div>
        </section>

        {/* Compliance bar */}
        <section style={{ background: '#fff', padding: '72px 24px', borderTop: '1px solid rgba(0,0,0,0.06)', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
          <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', gap: 0, justifyContent: 'space-around', flexWrap: 'wrap' }}>
            {[
              { label: 'UAE WPS Compliant',          sub: 'MOHRE / MOL certified format' },
              { label: 'Labour Law No. 33 of 2021',  sub: 'Leave and gratuity built in' },
              { label: 'Emiratization / Nafis',      sub: 'Quota tracking by sector' },
              { label: 'DHA / DOH / MOH Ready',     sub: 'Clinical licence tracking' },
            ].map(b => (
              <div key={b.label} style={{ textAlign: 'center', padding: '16px 28px' }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f', marginBottom: 4 }}>{b.label}</div>
                <div style={{ fontSize: 13, color: '#6e6e73' }}>{b.sub}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Pricing teaser */}
        <section style={{ background: '#f5f5f7', padding: '100px 24px' }}>
          <div style={{ maxWidth: 900, margin: '0 auto' }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16, textAlign: 'center' }}>Pricing</p>
            <h2 style={{ fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.1, letterSpacing: '-0.02em', textAlign: 'center', marginBottom: 12 }}>Simple pricing. No surprises.</h2>
            <p style={{ fontSize: 17, color: '#6e6e73', textAlign: 'center', marginBottom: 56, lineHeight: 1.6 }}>Start free. Upgrade when your clinic grows.</p>
            {renderPricingCards()}
            <div style={{ textAlign: 'center', marginTop: 32 }}>
              <button onClick={() => navigateToPage('pricing')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 15, color: '#0071e3', padding: 0, fontWeight: 500 }}>Compare plans ›</button>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section style={{
          minHeight: '50vh',
          background: '#06101f',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', padding: '80px 24px',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', width: '50vw', height: '50vw', maxWidth: 600, maxHeight: 600,
            borderRadius: '50%', top: '10%', right: '-10%',
            background: 'radial-gradient(circle, rgba(37,99,235,0.25) 0%, transparent 70%)',
            filter: 'blur(60px)',
          }} />
          <div style={{
            position: 'absolute', width: '40vw', height: '40vw', maxWidth: 500, maxHeight: 500,
            borderRadius: '50%', bottom: '5%', left: '-5%',
            background: 'radial-gradient(circle, rgba(6,182,212,0.20) 0%, transparent 70%)',
            filter: 'blur(50px)',
          }} />
          <div style={{ position: 'relative', zIndex: 1 }}>
            <h2 style={{ fontSize: 'clamp(28px, 5vw, 52px)', fontWeight: 700, color: '#f5f5f7', letterSpacing: '-0.02em', marginBottom: 20, lineHeight: 1.08 }}>
              Start running compliant HR today.
            </h2>
            <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.55)', marginBottom: 36 }}>No demo call needed — set up your clinic in minutes.</p>
            <button onClick={onGetStarted} style={{ background: '#fff', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 600, padding: '15px 36px', borderRadius: 980, color: '#06101f' }}>
              Get started free
            </button>
          </div>
        </section>
      </>
    );
  }

  // ── Features page ─────────────────────────────────────────────────────────

  function renderFeaturesPage() {
    return (
      <div style={{ paddingTop: 56, background: '#fff', minHeight: '100vh' }}>
        <div style={{ maxWidth: 980, margin: '0 auto', padding: '80px 24px' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>Features</p>
          <h1 style={{ fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 700, color: '#1d1d1f', letterSpacing: '-0.02em', marginBottom: 20, lineHeight: 1.08 }}>Twenty-four modules.<br />One platform.</h1>
          <p style={{ fontSize: 19, color: '#6e6e73', marginBottom: 72, lineHeight: 1.6, maxWidth: 560 }}>
            Every feature built around UAE Federal Labour Law, MOHRE compliance, and clinical workforce management — included in every plan.
          </p>
          <div style={{ borderTop: '1px solid rgba(0,0,0,0.08)' }}>
            {ALL_FEATURES.map(f => (
              <div key={f.title} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 40, padding: '28px 0', borderBottom: '1px solid rgba(0,0,0,0.08)', alignItems: 'start' }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#1d1d1f' }}>{f.title}</div>
                <div style={{ fontSize: 15, color: '#6e6e73', lineHeight: 1.65 }}>{f.desc}</div>
              </div>
            ))}
          </div>
          <div style={{ paddingTop: 64, textAlign: 'center' }}>
            <button onClick={onGetStarted} style={{ background: '#0071e3', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 500, padding: '14px 30px', borderRadius: 980, color: '#fff' }}>
              Get started free
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Pricing page ──────────────────────────────────────────────────────────

  function renderPricingPage() {
    return (
      <div style={{ paddingTop: 56, background: '#fff', minHeight: '100vh' }}>
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '80px 24px' }}>
          <h1 style={{ fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 700, color: '#1d1d1f', letterSpacing: '-0.02em', marginBottom: 14, textAlign: 'center', lineHeight: 1.08 }}>Pricing</h1>
          <p style={{ fontSize: 19, color: '#6e6e73', textAlign: 'center', marginBottom: 64, lineHeight: 1.6 }}>Start free. No credit card required.</p>
          {renderPricingCards()}
          <div style={{ marginTop: 48, padding: '32px', textAlign: 'center', borderTop: '1px solid rgba(0,0,0,0.08)' }}>
            <div style={{ fontSize: 17, fontWeight: 600, color: '#1d1d1f', marginBottom: 8 }}>Need more than 50 employees?</div>
            <div style={{ fontSize: 15, color: '#6e6e73' }}>Contact us at <strong>hello@workloop.ae</strong> for custom pricing.</div>
          </div>
        </div>
      </div>
    );
  }

  function renderPricingCards() {
    const cardBase = { borderRadius: 18, padding: '36px 32px', border: '1px solid rgba(0,0,0,0.10)' };
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
        <div style={{ ...cardBase, background: '#f5f5f7' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#6e6e73', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>Starter</div>
          <div style={{ fontSize: 48, fontWeight: 700, color: '#1d1d1f', letterSpacing: '-0.02em', marginBottom: 4 }}>AED 0</div>
          <div style={{ fontSize: 15, color: '#6e6e73', marginBottom: 32 }}>Forever free</div>
          <button onClick={onGetStarted} style={{ width: '100%', padding: '13px', borderRadius: 980, fontSize: 15, fontWeight: 500, cursor: 'pointer', background: 'none', border: '1px solid rgba(0,0,0,0.20)', color: '#1d1d1f', marginBottom: 28 }}>
            Get started
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {STARTER_FEATURES.map(f => (
              <div key={f} style={{ display: 'flex', gap: 10, fontSize: 14, color: '#3d3d3f' }}>
                <span style={{ color: '#0071e3', flexShrink: 0, fontWeight: 600 }}>+</span> {f}
              </div>
            ))}
          </div>
        </div>

        <div style={{ ...cardBase, background: '#0071e3', border: 'none', position: 'relative' }}>
          <div style={{ position: 'absolute', top: -1, left: '50%', transform: 'translateX(-50%)', background: '#fff', color: '#0071e3', fontSize: 11, fontWeight: 700, padding: '4px 14px', borderRadius: '0 0 8px 8px', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Most Popular</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.70)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>Growth</div>
          <div style={{ fontSize: 48, fontWeight: 700, color: '#fff', letterSpacing: '-0.02em', marginBottom: 4 }}>AED 99</div>
          <div style={{ fontSize: 15, color: 'rgba(255,255,255,0.70)', marginBottom: 32 }}>per month, billed annually</div>
          <button onClick={onGetStarted} style={{ width: '100%', padding: '13px', borderRadius: 980, fontSize: 15, fontWeight: 500, cursor: 'pointer', background: '#fff', border: 'none', color: '#0071e3', marginBottom: 28 }}>
            Start free trial
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {GROWTH_FEATURES.map(f => (
              <div key={f} style={{ display: 'flex', gap: 10, fontSize: 14, color: 'rgba(255,255,255,0.85)' }}>
                <span style={{ color: '#fff', flexShrink: 0, fontWeight: 600 }}>+</span> {f}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── About page ────────────────────────────────────────────────────────────

  function renderAboutPage() {
    return (
      <div style={{ paddingTop: 56, background: '#fff', minHeight: '100vh' }}>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#0071e3', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>About</p>
          <h1 style={{ fontSize: 'clamp(32px, 5vw, 48px)', fontWeight: 700, color: '#1d1d1f', letterSpacing: '-0.02em', marginBottom: 28, lineHeight: 1.1 }}>
            Built for the complexity of running a clinic in the UAE.
          </h1>
          {[
            { title: 'Healthcare-first.', body: 'DHA, DOH, and MOH licence tracking. BLS, ACLS, and PALS certification management. CME hour tracking. Staffing rules per department and shift. Workloop is not a general HR tool with a healthcare label — it was designed from day one for clinical teams.' },
            { title: 'Compliance built in.', body: 'Every feature starts from UAE Federal Decree-Law No. 33 of 2021. Leave entitlements, gratuity calculations, WPS SIF formatting, and Emiratization quotas are built in — not bolted on as settings you have to find and configure.' },
            { title: 'No setup call required.', body: 'Traditional HR software demands a week of onboarding and a dedicated implementation team. Workloop is different. Set up your company, departments, leave types, and payroll defaults in under fifteen minutes — with no sales call, no demo, and no consultants.' },
            { title: 'Three portals, one platform.', body: 'HR administrators, clinic managers, and employees each have their own dedicated portal. Managers approve leave and expenses for their direct reports. Employees submit requests, view payslips, clock in, and manage their own training — all from one URL.' },
            { title: 'Your data stays in the UAE.', body: 'All data is hosted on UAE infrastructure with row-level security. Your clinic\'s data is completely isolated from every other account — at the database level, not just the application layer.' },
          ].map(s => (
            <div key={s.title} style={{ paddingTop: 36, paddingBottom: 36, borderTop: '1px solid rgba(0,0,0,0.08)' }}>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1d1d1f', marginBottom: 12, letterSpacing: '-0.01em' }}>{s.title}</h2>
              <p style={{ fontSize: 17, color: '#6e6e73', lineHeight: 1.7 }}>{s.body}</p>
            </div>
          ))}
          <div style={{ paddingTop: 48, textAlign: 'center' }}>
            <button onClick={onGetStarted} style={{ background: '#0071e3', border: 'none', cursor: 'pointer', fontSize: 17, fontWeight: 500, padding: '14px 30px', borderRadius: 980, color: '#fff' }}>
              Get started free
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Footer ────────────────────────────────────────────────────────────────

  function renderFooter() {
    return (
      <footer style={{ background: '#f5f5f7', padding: '40px 80px', borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 32, marginBottom: 32 }}>
            <div style={{ maxWidth: 260 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#1d1d1f', marginBottom: 8 }}>Workloop</div>
              <div style={{ fontSize: 13, color: '#6e6e73', lineHeight: 1.6 }}>UAE clinic and hospital HRMS. WPS SIF generation, clinical credential tracking, shift rostering, and full labour law compliance.</div>
            </div>
            <div style={{ display: 'flex', gap: 64 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#86868b', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Product</div>
                {['home', 'features', 'pricing', 'about'].map(p => (
                  <div key={p} style={{ marginBottom: 8 }}>
                    <button onClick={() => navigateToPage(p)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: '#6e6e73', padding: 0 }}>
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </button>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#86868b', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 12 }}>Contact</div>
                <div style={{ fontSize: 13, color: '#6e6e73', marginBottom: 8 }}>hello@workloop.ae</div>
                <div style={{ fontSize: 13, color: '#6e6e73' }}>Dubai, UAE</div>
              </div>
            </div>
          </div>
          <div style={{ borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: 20, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <span style={{ fontSize: 12, color: '#86868b' }}>© 2026 Workloop. All rights reserved.</span>
            <span style={{ fontSize: 12, color: '#86868b' }}>UAE Federal Decree-Law No. 33 of 2021 compliant</span>
          </div>
        </div>
      </footer>
    );
  }

  // ── Root render ───────────────────────────────────────────────────────────

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif', background: '#fff', color: '#1d1d1f', minHeight: '100vh' }}>
      <style>{`
        @keyframes orbFloat1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -40px) scale(1.05); }
          66% { transform: translate(-20px, 20px) scale(0.95); }
        }
        @keyframes orbFloat2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(-25px, 30px) scale(1.08); }
          66% { transform: translate(35px, -15px) scale(0.92); }
        }
        @keyframes orbFloat3 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-30px, -25px) scale(1.1); }
        }
        @keyframes ribbonDrift1 {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-24px); }
        }
        @keyframes ribbonDrift2 {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(20px); }
        }
        @keyframes ribbonDrift3 {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-16px); }
        }
        @keyframes landingPageEnter {
          from { opacity: 0; transform: translateY(14px); filter: blur(2px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
        .landing-page-content {
          opacity: 1;
          transform: translateY(0);
          transition: opacity 180ms ease, transform 180ms ease, filter 180ms ease;
          will-change: opacity, transform;
        }
        .landing-page-content.leaving {
          opacity: 0;
          transform: translateY(-8px);
          filter: blur(1px);
          pointer-events: none;
        }
        .landing-page-content.entering {
          animation: landingPageEnter 420ms cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        .landing-nav-link {
          position: relative;
        }
        .landing-nav-link::after {
          content: '';
          position: absolute;
          left: 16px;
          right: 16px;
          bottom: -10px;
          height: 2px;
          border-radius: 2px;
          background: currentColor;
          opacity: 0;
          transform: scaleX(0.25);
          transition: opacity 240ms ease, transform 320ms cubic-bezier(0.22, 1, 0.36, 1);
        }
        .landing-nav-link.active::after {
          opacity: 0.8;
          transform: scaleX(1);
        }
        @media (prefers-reduced-motion: reduce) {
          .landing-page-content,
          .landing-page-content.entering,
          .landing-nav-link::after {
            animation: none !important;
            transition: none !important;
            transform: none !important;
            filter: none !important;
          }
        }
      `}</style>
      {renderNav()}

      <div key={page} className={`landing-page-content ${pageTransition}`} aria-live="polite">
        {page === 'home'     && renderHome()}
        {page === 'features' && renderFeaturesPage()}
        {page === 'pricing'  && renderPricingPage()}
        {page === 'about'    && renderAboutPage()}
        {renderFooter()}
      </div>
    </div>
  );
}
