import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  BookOpenCheck,
  Check,
  CheckCheck,
  GitBranch,
  History,
  Layers3,
  ShieldCheck,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import styles from "./landing.module.css";

export const metadata: Metadata = {
  title: "PolicyOS — Every policy. The right people.",
  description:
    "Turn employee information into clear, consistent policy assignments. Define rules, preview changes, and understand every decision with PolicyOS.",
};

const features = [
  {
    icon: GitBranch,
    title: "Rules that do the repeat work.",
    copy: "Build policies around employee attributes and group membership. Keep assignments consistent as your organization changes.",
  },
  {
    icon: SlidersHorizontal,
    title: "See the impact before you act.",
    copy: "Preview who a change affects and resolve competing priorities before saving.",
  },
  {
    icon: History,
    title: "An answer behind every assignment.",
    copy: "Trace assignments to their source. Review policy history, manual overrides, and recorded changes in one place.",
  },
];

export default function LandingPage() {
  return (
    <div className={styles.landing}>
      <a className={styles.skipLink} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <Link className={styles.brand} href="/" aria-label="PolicyOS home">
          <span className={styles.brandMark}>P</span>PolicyOS
        </Link>
        <nav className={styles.navigation} aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#how-it-works">How it works</a>
          <Link href="/learn" target="_blank" rel="noopener noreferrer">
            Learn<span className="sr-only"> (opens in a new tab)</span>
          </Link>
        </nav>
        <div className={styles.headerActions}>
          <Link className={styles.signIn} href="/login">
            Sign in
          </Link>
          <Link className={styles.primaryButton} href="/signup">
            Sign up <ArrowRight size={16} />
          </Link>
        </div>
      </header>
      <main id="main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>
              <span /> POLICY ASSIGNMENTS, SIMPLIFIED
            </p>
            <h1 id="hero-title">
              Every policy.
              <br />
              The <span>right people.</span>
            </h1>
            <p className={styles.heroDescription}>
              Your people change. Their policies should keep up. Turn employee information into
              consistent assignments—with a clear reason behind every decision.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryButton} href="/signup">
                Sign up for PolicyOS <ArrowRight size={18} />
              </Link>
              <Link className={styles.secondaryButton} href="/login">
                Sign in <ArrowRight size={17} />
              </Link>
            </div>
            <div className={styles.heroNotes}>
              <span>
                <Check size={15} /> Preview before applying
              </span>
              <span>
                <Check size={15} /> Keep a clear audit trail
              </span>
            </div>
          </div>
          <div className={styles.visual} aria-label="Illustrative policy assignment workflow">
            <div className={styles.visualHeading}>
              <span>
                <span className={styles.liveDot} /> THE ASSIGNMENT ENGINE
              </span>
              <span>Example workflow</span>
            </div>
            <div className={styles.personCard}>
              <div className={styles.avatar}>ER</div>
              <div>
                <strong>Employee record</strong>
                <span>Facts supplied by your system</span>
              </div>
              <span className={styles.personLabel}>Employee</span>
            </div>
            <div className={styles.connector}>
              <span />
              <ArrowDown size={17} />
            </div>
            <div className={styles.engineCard}>
              <div className={styles.engineTitle}>
                <span className={styles.engineIcon}>
                  <Layers3 size={22} />
                </span>
                <div>
                  <strong>Right rules. Resolved.</strong>
                  <span>Employee attributes → policy matches</span>
                </div>
              </div>
              <div className={styles.conditions}>
                <span>Department = Engineering</span>
                <span>Employment = Full-time</span>
              </div>
            </div>
            <div className={styles.connector}>
              <span />
              <ArrowDown size={17} />
            </div>
            <div className={styles.assignmentCard}>
              <div className={styles.assignmentHeader}>
                <strong>Policy assignments</strong>
                <span>
                  <CheckCheck size={15} /> Resolved
                </span>
              </div>
              {[
                "Engineering application access",
                "Full-time benefits",
                "Standard pay schedule",
              ].map((name) => (
                <div className={styles.assignmentRow} key={name}>
                  <span className={styles.checkIcon}>
                    <Check size={13} />
                  </span>
                  {name}
                  <span>Policy-derived</span>
                </div>
              ))}
            </div>
            <div className={styles.explanation}>
              <ShieldCheck size={16} />
              <span>Every assignment has a reason. Every change leaves a trail.</span>
            </div>
          </div>
        </section>
        <div className={styles.useCases}>
          <span>ONE ENGINE. ACROSS YOUR ORGANIZATION.</span>
          <div>
            <span>
              <Users size={19} /> People operations
            </span>
            <span>
              <ShieldCheck size={19} /> IT & access
            </span>
            <span>
              <Layers3 size={19} /> Payroll & benefits
            </span>
          </div>
        </div>
        <section id="platform" className={styles.platform} aria-labelledby="platform-title">
          <div className={styles.sectionHeading}>
            <p className={styles.eyebrow}>LESS MANUAL WORK. MORE CLARITY.</p>
            <h2 id="platform-title">
              From scattered rules
              <br />
              to a single source of truth.
            </h2>
            <p>
              Give your teams a shared system for defining, reviewing, and explaining employee
              policy assignments.
            </p>
          </div>
          <div className={styles.features}>
            {features.map(({ icon: Icon, title, copy }, index) => (
              <article key={title}>
                <div className={styles.featureTop}>
                  <Icon size={24} strokeWidth={1.6} />
                  <span>0{index + 1}</span>
                </div>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="how-it-works" className={styles.workflow} aria-labelledby="workflow-title">
          <div>
            <p className={styles.eyebrow}>A CLEAR PATH FROM RULE TO RESULT</p>
            <h2 id="workflow-title">
              Set the rules.
              <br />
              Know the outcome.
            </h2>
          </div>
          <ol>
            {[
              {
                title: "Define your policies",
                copy: "Choose employee conditions, assignment values, and priorities.",
              },
              {
                title: "Preview and review",
                copy: "Understand the impact before saving sensitive changes.",
              },
              {
                title: "Apply with confidence",
                copy: "Resolve assignments and inspect the explanation behind each result.",
              },
            ].map((step, index) => (
              <li key={step.title}>
                <span>0{index + 1}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
        <section className={styles.docsSection} aria-labelledby="docs-title">
          <span className={styles.docsIcon}>
            <BookOpenCheck size={28} strokeWidth={1.7} />
          </span>
          <div className={styles.docsContent}>
            <p className={styles.eyebrow}>LEARN FROM FIRST PRINCIPLES</p>
            <h2 id="docs-title">Learn PolicyOS at your own pace.</h2>
            <p>
              Explore a curriculum that starts with the domain, connects each concept to PolicyOS,
              and explains how the application puts those concepts into practice.
            </p>
            <div className={styles.docsTopics} aria-label="Learning sections">
              <span>Concepts</span>
              <span>PolicyOS</span>
            </div>
          </div>
          <Link
            className={styles.docsButton}
            href="/learn"
            target="_blank"
            rel="noopener noreferrer"
          >
            Explore the curriculum <ArrowRight size={17} />
            <span className="sr-only"> (opens in a new tab)</span>
          </Link>
        </section>
        <section className={styles.cta} aria-labelledby="cta-title">
          <div>
            <p className={styles.eyebrow}>MAKE EVERY ASSIGNMENT MAKE SENSE</p>
            <h2 id="cta-title">Bring clarity to your policies.</h2>
            <p>One place for your rules, your people, and the decisions that connect them.</p>
          </div>
          <Link className={styles.primaryButton} href="/signup">
            Sign up <ArrowRight size={18} />
          </Link>
        </section>
      </main>
      <footer className={styles.footer}>
        <Link className={styles.brand} href="/">
          <span className={styles.brandMark}>P</span>PolicyOS
        </Link>
        <span>Every employee policy assignment, resolved and explained.</span>
        <div>
          <Link href="/login">Sign in</Link>
          <Link href="/signup">Sign up</Link>
        </div>
      </footer>
    </div>
  );
}
