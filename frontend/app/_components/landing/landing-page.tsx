import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BookOpenCheck,
  Bot,
  Building2,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  Eye,
  FileCheck2,
  GitBranch,
  History,
  KeyRound,
  Layers3,
  LockKeyhole,
  MapPin,
  Network,
  RefreshCw,
  Scale,
  Server,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import styles from "../../landing.module.css";

const proofItems = [
  {
    icon: CalendarClock,
    title: "Date-effective versions",
    detail: "Rules evolve without rewriting history",
  },
  { icon: Layers3, title: "One + many values", detail: "Explicit cardinality for every field" },
  {
    icon: GitBranch,
    title: "Rich workforce context",
    detail: "Facts, tenure, groups, and org structure",
  },
  {
    icon: CircleAlert,
    title: "Visible conflicts",
    detail: "Ambiguity stops instead of disappearing",
  },
  { icon: Eye, title: "Preview before commit", detail: "Real domain behavior, always rolled back" },
  {
    icon: History,
    title: "Stored provenance",
    detail: "The original decision, preserved over time",
  },
];

const resolutionSteps = [
  {
    number: "01",
    title: "Employee facts",
    detail: "Department, location, tenure, manager, and org context",
  },
  {
    number: "02",
    title: "Effective versions",
    detail: "The policy definitions active on the evaluation date",
  },
  {
    number: "03",
    title: "Direct + group matches",
    detail: "Every matching rule and attached group origin",
  },
  {
    number: "04",
    title: "Candidate values",
    detail: "All possible outcomes, retained for explanation",
  },
  {
    number: "05",
    title: "Resolve",
    detail: "Cardinality, priority, and explicit conflict semantics",
  },
  {
    number: "06",
    title: "Apply overrides",
    detail: "Authorized exceptions after policy resolution",
  },
  {
    number: "07",
    title: "Record the decision",
    detail: "Temporal assignment plus its explanation snapshot",
  },
];

const changeTriggers = [
  { icon: MapPin, label: "Location" },
  { icon: Building2, label: "Department" },
  { icon: Clock3, label: "Tenure" },
  { icon: Network, label: "Manager" },
  { icon: Users, label: "Group" },
  { icon: CalendarClock, label: "Policy date" },
];

const trustBadges = [
  "OAuth + PKCE",
  "52 typed tools",
  "Same RBAC",
  "Preview-first",
  "Fully audited",
];

function Brand() {
  return (
    <Link className={styles.brand} href="/" aria-label="PolicyOS home">
      <span className={styles.brandMark}>P</span>
      <span>PolicyOS</span>
    </Link>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className={styles.eyebrow}>
      <span aria-hidden="true" />
      {children}
    </p>
  );
}

function HeroDecision() {
  return (
    <div
      className={styles.heroVisual}
      aria-label="PolicyOS assignment explanation for Rafael Morales"
    >
      <div className={styles.visualTopbar}>
        <span>Assignment detail</span>
        <span className={styles.engineStatus}>
          <span aria-hidden="true" /> Engine ready
        </span>
      </div>
      <div className={styles.personBar}>
        <span className={styles.avatar}>RM</span>
        <div>
          <strong>Rafael Morales</strong>
          <span>Field Operations · Manager</span>
        </div>
        <span className={styles.dateChip}>As of today</span>
      </div>
      <div className={styles.assignmentResult}>
        <div className={styles.assignmentMeta}>
          <span>Expense Approval Limit</span>
          <span className={styles.resolvedBadge}>
            <Check size={12} /> Resolved
          </span>
        </div>
        <div className={styles.assignmentValueRow}>
          <strong>USD 10,000</strong>
          <span>One value</span>
        </div>
        <div className={styles.winnerCard}>
          <div className={styles.winnerHeader}>
            <span>
              <Sparkles size={15} /> Winning policy
            </span>
            <span>Priority 45</span>
          </div>
          <strong>People Manager Responsibilities</strong>
          <div className={styles.evidenceRow}>
            <span>Matched evidence</span>
            <span>Is Manager</span>
            <strong>Yes</strong>
          </div>
        </div>
        <div className={styles.candidateRow}>
          <div>
            <span>Also evaluated</span>
            <strong>Field Operations Readiness</strong>
          </div>
          <div>
            <span>USD 2,500</span>
            <strong>Priority 35 · Lower priority</strong>
          </div>
        </div>
      </div>
      <div className={styles.explainBar}>
        <span>
          <FileCheck2 size={16} /> Candidate values, evidence, and decision strategy retained
        </span>
        <span>
          Explain decision <ChevronRight size={15} />
        </span>
      </div>
    </div>
  );
}

function ProductEvidence() {
  return (
    <section
      id="explainability"
      className={styles.evidenceSection}
      aria-labelledby="evidence-title"
    >
      <div className={styles.sectionIntroRow}>
        <div>
          <Eyebrow>Real product evidence</Eyebrow>
          <h2 id="evidence-title">See the decision—not just the result.</h2>
        </div>
        <p>
          PolicyOS exposes the workflows administrators actually need: inspect a winner, preview a
          risky change, understand an exception, and see who a policy reaches.
        </p>
      </div>
      <div className={styles.evidenceLayout}>
        <article className={styles.primaryEvidence}>
          <div className={styles.imageFrame}>
            <Image
              src="/landing/product-evidence/assignment-explanation.jpg"
              alt="PolicyOS assignment explanation showing Rafael Morales's USD 10,000 expense limit, the winning priority-45 manager policy, matched evidence, and candidate decision"
              width={1280}
              height={720}
              sizes="(max-width: 800px) 100vw, 65vw"
            />
          </div>
          <div className={styles.evidenceCopy}>
            <span className={styles.evidenceIndex}>01</span>
            <div>
              <h3>Follow every decision to its source.</h3>
              <p>
                The stored explanation includes the winning version, matched facts, group origins,
                candidates, priorities, and selection strategy used at resolution time.
              </p>
            </div>
          </div>
        </article>
        <div className={styles.supportingEvidence}>
          <article>
            <div className={styles.imageFrame}>
              <Image
                src="/landing/product-evidence/change-preview.jpg"
                alt="PolicyOS preview showing three assignment fields that would change if Priya Raman moved from Engineering to Product"
                width={1280}
                height={720}
                sizes="(max-width: 800px) 100vw, 35vw"
              />
            </div>
            <div>
              <span className={styles.evidenceIndex}>02 · Preview</span>
              <h3>Inspect impact before saving.</h3>
              <p>
                Priya&apos;s department move runs through the real mutation path, then rolls back.
              </p>
            </div>
          </article>
          <article>
            <div className={styles.imageFrame}>
              <Image
                src="/landing/product-evidence/manual-override.jpg"
                alt="PolicyOS showing Priya Raman's USD 5,000 manual override and the USD 2,500 policy result it replaced"
                width={1280}
                height={720}
                sizes="(max-width: 800px) 100vw, 35vw"
              />
            </div>
            <div>
              <span className={styles.evidenceIndex}>03 · Provenance</span>
              <h3>Make exceptions visible.</h3>
              <p>
                A manual USD 5,000 value stays connected to the USD 2,500 policy result it replaced.
              </p>
            </div>
          </article>
        </div>
      </div>
      <article className={styles.policyEvidence}>
        <div>
          <span className={styles.evidenceIndex}>04 · Version + impact</span>
          <h3>Understand a policy as a dated system change.</h3>
          <p>
            People Manager Responsibilities shows its conditions, assignment outputs, effective
            date, priority, version, and affected population in one review surface.
          </p>
        </div>
        <div className={styles.imageFrame}>
          <Image
            src="/landing/product-evidence/policy-impact-version.jpg"
            alt="People Manager Responsibilities policy showing its manager rule, three assignment outputs, effective date, version, priority, and population impact"
            width={1280}
            height={720}
            sizes="(max-width: 800px) 100vw, 58vw"
          />
        </div>
      </article>
    </section>
  );
}

export function LandingPage() {
  return (
    <div className={styles.landing}>
      <a className={styles.skipLink} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <Brand />
        <nav className={styles.navigation} aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#how-it-works">How it works</a>
          <a href="#explainability">Explainability</a>
          <a href="#agent-ready">Agent-ready</a>
          <Link href="/learn" target="_blank" rel="noopener noreferrer">
            Learn<span className="sr-only"> (opens in a new tab)</span>
          </Link>
        </nav>
        <div className={styles.headerActions}>
          <Link className={styles.signIn} href="/login">
            Sign in
          </Link>
          <Link className={styles.primaryButton} href="/login">
            Explore the demo <ArrowRight size={16} />
          </Link>
        </div>
      </header>

      <main id="main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <Eyebrow>Policy assignment infrastructure</Eyebrow>
            <h1 id="hero-title">
              Policies that follow your people—<span>and explain every decision.</span>
            </h1>
            <p className={styles.heroDescription}>
              Define date-effective rules across employee facts, location, tenure, groups, and org
              structure. Preview their impact, reconcile every change, and trace each assignment to
              its source.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryButton} href="/login">
                Explore the demo <ArrowRight size={18} />
              </Link>
              <a className={styles.secondaryButton} href="#how-it-works">
                See how it works <ChevronRight size={17} />
              </a>
            </div>
            <ul className={styles.heroProof} aria-label="PolicyOS product qualities">
              <li>
                <CheckCircle2 size={14} /> Deterministic resolution
              </li>
              <li>
                <CheckCircle2 size={14} /> Preview before commit
              </li>
              <li>
                <CheckCircle2 size={14} /> Complete provenance
              </li>
              <li>
                <CheckCircle2 size={14} /> Agent-ready through MCP
              </li>
            </ul>
          </div>
          <HeroDecision />
        </section>

        <section id="platform" className={styles.proofRail} aria-label="PolicyOS capabilities">
          {proofItems.map(({ icon: Icon, title, detail }) => (
            <article key={title}>
              <Icon size={18} strokeWidth={1.7} />
              <div>
                <strong>{title}</strong>
                <span>{detail}</span>
              </div>
            </article>
          ))}
        </section>

        <section
          id="how-it-works"
          className={styles.resolutionSection}
          aria-labelledby="resolution-title"
        >
          <div className={styles.sectionIntroRow}>
            <div>
              <Eyebrow>Deterministic by design</Eyebrow>
              <h2 id="resolution-title">From workforce context to one explainable outcome.</h2>
            </div>
            <p>
              The resolver is a transparent policy engine—not an AI model. The same inputs always
              produce the same assignments or the same explicit conflict.
            </p>
          </div>
          <ol className={styles.pipeline}>
            {resolutionSteps.map((step) => (
              <li key={step.number}>
                <span className={styles.stepNumber}>{step.number}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.detail}</p>
                </div>
                <ChevronRight className={styles.stepArrow} size={17} aria-hidden="true" />
              </li>
            ))}
          </ol>
          <div className={styles.cardinalityGrid}>
            <article className={styles.cardinalityCard}>
              <div className={styles.cardinalityIcon}>
                <Scale size={22} />
              </div>
              <div>
                <span className={styles.cardLabel}>One-value fields</span>
                <h3>Priority decides—until equal priority disagrees.</h3>
                <p>
                  The highest priority wins only when candidates at that priority agree. Different
                  values at equal priority produce a structured conflict that must be resolved.
                </p>
              </div>
              <div className={styles.oneValueExample} aria-label="One-value conflict example">
                <div>
                  <span>Policy A</span>
                  <strong>Semi-monthly</strong>
                  <small>Priority 40</small>
                </div>
                <div>
                  <span>Policy B</span>
                  <strong>Biweekly</strong>
                  <small>Priority 40</small>
                </div>
                <div className={styles.conflictResult}>
                  <CircleAlert size={16} />
                  <strong>Conflict surfaced</strong>
                  <span>No silent tie-break</span>
                </div>
              </div>
            </article>
            <article className={styles.cardinalityCard}>
              <div className={styles.cardinalityIcon}>
                <Layers3 size={22} />
              </div>
              <div>
                <span className={styles.cardLabel}>Many-value fields</span>
                <h3>Unique values combine. Provenance stays deterministic.</h3>
                <p>
                  All unique values join the assignment. If policies contribute the same value,
                  PolicyOS records one source by priority, then policy-version ID.
                </p>
              </div>
              <div className={styles.manyValueExample} aria-label="Many-value resolution example">
                <span>Slack</span>
                <span>Google Workspace</span>
                <span>GitHub Enterprise</span>
                <div>
                  <CheckCircle2 size={15} /> 3 unique values · sources retained
                </div>
              </div>
            </article>
          </div>
        </section>

        <ProductEvidence />

        <section className={styles.changeSection} aria-labelledby="change-title">
          <div className={styles.changeIntro}>
            <Eyebrow>Reconciliation over time</Eyebrow>
            <h2 id="change-title">When the workforce changes, assignments keep up.</h2>
            <p>
              PolicyOS is not a one-time calculator. Every supported change flows through the same
              resolver and reconciliation path, preserving what changed and why.
            </p>
          </div>
          <div className={styles.changeFlow}>
            <div className={styles.triggerGrid} aria-label="Workforce change triggers">
              {changeTriggers.map(({ icon: Icon, label }) => (
                <span key={label}>
                  <Icon size={17} /> {label}
                </span>
              ))}
            </div>
            <div className={styles.flowConnector}>
              <span />
              <ChevronRight size={20} />
            </div>
            <div className={styles.reconcileCore}>
              <RefreshCw size={22} />
              <span>Same resolver</span>
              <strong>Reconcile desired state</strong>
              <small>Keep equal rows · close changed rows · insert replacements</small>
            </div>
            <div className={styles.flowConnector}>
              <span />
              <ChevronRight size={20} />
            </div>
            <div className={styles.timelineResult}>
              <span>Assignment history</span>
              <div>
                <i />
                <strong>Previous decision</strong>
                <small>Closed at change time</small>
              </div>
              <div>
                <i />
                <strong>Current decision</strong>
                <small>New explanation snapshot</small>
              </div>
            </div>
          </div>
          <p className={styles.boundaryNote}>
            <CircleAlert size={15} /> Future calculations use current employee facts with future
            policy versions and date-derived tenure. Historical employee facts are not independently
            versioned; recorded assignment history remains authoritative.
          </p>
        </section>

        <section id="agent-ready" className={styles.agentSection} aria-labelledby="agent-title">
          <div className={styles.agentHeading}>
            <Eyebrow>AI-native operations</Eyebrow>
            <h2 id="agent-title">Agent-ready, without an AI backdoor.</h2>
            <p>
              The optional Streamable HTTP MCP server lets compatible agents inspect, explain,
              preview, and administer PolicyOS. It is an interface over the application—not a second
              implementation of policy logic.
            </p>
          </div>
          <div className={styles.agentGrid}>
            <div className={styles.transcript}>
              <div className={styles.transcriptTop}>
                <span>
                  <Bot size={17} /> Agent session
                </span>
                <span>
                  <span aria-hidden="true" /> User-bound
                </span>
              </div>
              <div className={styles.userMessage}>
                <span>You</span>
                <p>“Preview moving Priya from Engineering to Product. Do not save anything.”</p>
              </div>
              <div className={styles.agentMessage}>
                <span>
                  <span className={styles.miniBrand}>P</span> PolicyOS
                </span>
                <p>
                  <strong>3 assignment fields would change.</strong> No data was persisted.
                </p>
                <ul>
                  <li>
                    <span>Device Profile</span>
                    <strong>Engineering Workstation → Managed Standard Laptop</strong>
                  </li>
                  <li>
                    <span>Application Access</span>
                    <strong>Access set updated</strong>
                  </li>
                  <li>
                    <span>Information Access</span>
                    <strong>Engineering access removed</strong>
                  </li>
                </ul>
                <div className={styles.toolReceipt}>
                  <CheckCircle2 size={15} /> preview_change · read-only result
                </div>
              </div>
            </div>
            <div className={styles.agentTrust}>
              <div className={styles.trustPath} aria-label="MCP authorization path">
                <div>
                  <Bot size={18} />
                  <span>MCP client</span>
                </div>
                <ChevronRight size={16} />
                <div>
                  <KeyRound size={18} />
                  <span>OAuth user</span>
                </div>
                <ChevronRight size={16} />
                <div>
                  <Server size={18} />
                  <span>MCP adapter</span>
                </div>
                <ChevronRight size={16} />
                <div>
                  <ShieldCheck size={18} />
                  <span>FastAPI</span>
                </div>
              </div>
              <div className={styles.trustStatement}>
                <LockKeyhole size={24} />
                <div>
                  <h3>Same authorization. Same domain services.</h3>
                  <p>
                    Agents inherit the connected user&apos;s permissions and employee visibility.
                    The adapter never accesses PostgreSQL directly; every tool call passes through
                    FastAPI validation, RBAC, reconciliation, structured errors, and auditing.
                  </p>
                </div>
              </div>
              <div className={styles.trustBadges}>
                {trustBadges.map((badge) => (
                  <span key={badge}>{badge}</span>
                ))}
              </div>
              <p className={styles.credentialNote}>
                Login, MFA, and consent stay in the browser. Credentials and MFA codes never pass
                through the agent. Tool schemas distinguish read-only, mutating, and destructive
                work.
              </p>
            </div>
          </div>
          <div className={styles.webMcpNote}>
            <Sparkles size={17} />
            <p>
              <strong>A separate in-browser enhancement.</strong> PolicyOS also registers five
              WebMCP navigation tools to help compatible browsers open onboarding, policy authoring,
              assignments, groups, and field setup. These navigate the visible UI; the external MCP
              server handles authenticated product operations through FastAPI.
            </p>
          </div>
        </section>

        <section className={styles.architectureSection} aria-labelledby="architecture-title">
          <div className={styles.architectureCopy}>
            <Eyebrow>One trusted system</Eyebrow>
            <h2 id="architecture-title">Every interface converges on the same boundary.</h2>
            <p>
              Browser, worker, and agent operations share the same domain behavior. PostgreSQL is
              the source of truth; FastAPI owns validation and authorization; outcomes and material
              changes are audited.
            </p>
            <Link
              href="/learn"
              className={styles.textLink}
              target="_blank"
              rel="noopener noreferrer"
            >
              Explore the system from first principles <ArrowRight size={16} />
              <span className="sr-only"> (opens in a new tab)</span>
            </Link>
          </div>
          <div className={styles.architectureDiagram} aria-label="PolicyOS architecture overview">
            <div className={styles.interfaceNodes}>
              <span>
                Browser<small>HTTP-only session</small>
              </span>
              <span>
                Worker<small>scheduled reconciliation</small>
              </span>
              <span>
                MCP adapter<small>user-bound OAuth</small>
              </span>
            </div>
            <div className={styles.architectureArrow}>
              <span />
              <ChevronRight size={19} />
            </div>
            <div className={styles.apiNode}>
              <ShieldCheck size={22} />
              <strong>FastAPI</strong>
              <span>Authorization + validation boundary</span>
            </div>
            <div className={styles.architectureArrow}>
              <span />
              <ChevronRight size={19} />
            </div>
            <div className={styles.serviceNodes}>
              <span>
                <GitBranch size={17} /> Policy engine
              </span>
              <span>
                <RefreshCw size={17} /> Reconciliation
              </span>
              <span>
                <FileCheck2 size={17} /> Audit writes
              </span>
            </div>
            <div className={styles.architectureArrow}>
              <span />
              <ChevronRight size={19} />
            </div>
            <div className={styles.databaseNode}>
              <Database size={22} />
              <strong>PostgreSQL</strong>
              <span>Source of truth</span>
            </div>
          </div>
        </section>

        <section className={styles.learnSection} aria-labelledby="learn-title">
          <div className={styles.learnIcon}>
            <BookOpenCheck size={25} />
          </div>
          <div>
            <Eyebrow>Learn the model</Eyebrow>
            <h2 id="learn-title">Understand policy assignment from first principles.</h2>
            <p>
              A focused curriculum connects domain concepts to the way PolicyOS handles rules,
              cardinality, time, reconciliation, explanations, and authorization.
            </p>
          </div>
          <Link
            href="/learn"
            className={styles.secondaryButton}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open Learn <ArrowRight size={16} />
            <span className="sr-only"> (opens in a new tab)</span>
          </Link>
        </section>

        <section className={styles.cta} aria-labelledby="cta-title">
          <div>
            <Eyebrow>From rule to reason</Eyebrow>
            <h2 id="cta-title">See every rule become an explainable decision.</h2>
            <p>Explore the seeded Cedar Harbor workspace and follow real assignments end to end.</p>
          </div>
          <div className={styles.ctaActions}>
            <Link className={styles.primaryButton} href="/login">
              Explore the demo <ArrowRight size={18} />
            </Link>
            <Link
              className={styles.secondaryButton}
              href="/learn"
              target="_blank"
              rel="noopener noreferrer"
            >
              Learn how it works <ChevronRight size={17} />
              <span className="sr-only"> (opens in a new tab)</span>
            </Link>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <Brand />
        <span>Workforce policy assignments, resolved and explained.</span>
        <div>
          <Link href="/login">Sign in</Link>
          <Link href="/learn" target="_blank" rel="noopener noreferrer">
            Learn<span className="sr-only"> (opens in a new tab)</span>
          </Link>
        </div>
      </footer>
    </div>
  );
}
