import Image from "next/image";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  CircleAlert,
  FileClock,
  Fingerprint,
  GitCompareArrows,
  KeyRound,
  Layers3,
  LockKeyhole,
  Network,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import styles from "../../landing.module.css";
import { MobileNavigation } from "./mobile-navigation";

const pillars = [
  {
    number: "01",
    icon: Network,
    title: "Context becomes policy input",
    copy: "Resolve assignments from employee facts, tenure, reporting lines, and inherited group membership—not scattered spreadsheets.",
  },
  {
    number: "02",
    icon: ScanSearch,
    title: "Impact is visible before commit",
    copy: "Run proposed changes through the real resolution path and inspect every affected assignment before anything is saved.",
  },
  {
    number: "03",
    icon: Layers3,
    title: "Priority resolves overlap",
    copy: "Use explicit precedence for competing policies. Equal-priority disagreement becomes a visible conflict, never a silent guess.",
  },
  {
    number: "04",
    icon: Fingerprint,
    title: "Every outcome keeps its reason",
    copy: "Preserve the winning version, matched evidence, candidate values, group origin, overrides, and resolution strategy.",
  },
];

const workflow = [
  [
    "Define",
    "Assignment fields",
    "Set each governed outcome and whether it accepts one value or many.",
  ],
  [
    "Describe",
    "Workforce context",
    "Bring together employee facts, reporting structure, locations, and groups.",
  ],
  [
    "Author",
    "Policies + priorities",
    "Create dated rules with explicit conditions, outputs, and precedence.",
  ],
  ["Preview", "Population impact", "Inspect who changes, what changes, and which policy will win."],
  [
    "Activate",
    "Decisions + audit",
    "Publish the version and retain the history behind every result.",
  ],
];

const explanationQuestions = [
  ["Which policy won?", "People Manager Responsibilities · v2"],
  ["Which fact matched?", "Is Manager = Yes"],
  ["What lost?", "Field Operations Readiness · priority 35"],
  ["Was a group involved?", "No · direct condition match"],
  ["Was it overridden?", "No manual override"],
];

function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link
      className={`${styles.brand}${inverse ? ` ${styles.brandInverse}` : ""}`}
      href="/"
      aria-label="PolicyOS home"
    >
      <span className={styles.brandMark} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>PolicyOS</span>
    </Link>
  );
}

function Eyebrow({ children, inverse = false }: { children: React.ReactNode; inverse?: boolean }) {
  return (
    <p className={`${styles.eyebrow}${inverse ? ` ${styles.eyebrowInverse}` : ""}`}>
      <span aria-hidden="true">#</span> {children}
    </p>
  );
}

function ProductWindow({
  src,
  alt,
  label,
  figure,
  priority = false,
}: {
  src: string;
  alt: string;
  label: string;
  figure: string;
  priority?: boolean;
}) {
  return (
    <figure className={styles.productWindow}>
      <figcaption>
        <span>{figure}</span>
        <span>{label}</span>
        <span aria-hidden="true">⌗</span>
      </figcaption>
      <div className={styles.productImage}>
        <Image
          src={src}
          alt={alt}
          fill
          priority={priority}
          sizes="(max-width: 760px) 94vw, (max-width: 1100px) 88vw, 1120px"
        />
      </div>
    </figure>
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
        <nav className={styles.desktopNavigation} aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#workflow">How it works</a>
          <a href="#explainability">Explainability</a>
          <a href="#governance">Governance</a>
          <Link href="/learn">Learn</Link>
        </nav>
        <div className={styles.headerActions}>
          <Link href="/login">Sign in</Link>
          <Link className={styles.headerCta} href="/signup">
            Get started <ArrowUpRight size={15} />
          </Link>
        </div>
        <MobileNavigation />
      </header>

      <main id="main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <Eyebrow>Governed assignment infrastructure</Eyebrow>
            <h1 id="hero-title">Turn workforce context into decisions you can defend.</h1>
            <p>
              PolicyOS converts employee facts and organizational context into governed
              assignments—then shows the exact policy, priority, and evidence behind every result.
            </p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryCta} href="/signup">
                Get started <ArrowRight size={17} />
              </Link>
              <a className={styles.secondaryCta} href="#product-proof">
                See the product <ArrowDown size={16} />
              </a>
            </div>
          </div>
          <aside className={styles.heroBrief} aria-label="PolicyOS product summary">
            <span className={styles.briefLabel}>System brief / 001</span>
            <p>
              Built for HR, IT, compliance, and operations teams that need policy assignment to be
              consistent, reviewable, and accountable.
            </p>
            <dl>
              <div>
                <dt>Input</dt>
                <dd>People + org context</dd>
              </div>
              <div>
                <dt>Method</dt>
                <dd>Rules + explicit priority</dd>
              </div>
              <div>
                <dt>Output</dt>
                <dd>Assignments + provenance</dd>
              </div>
            </dl>
          </aside>

          <div className={styles.heroProof} id="product-proof">
            <div className={styles.heroProofNote}>
              <span>Live product / seeded workspace</span>
              <strong>One decision. Every reason intact.</strong>
            </div>
            <ProductWindow
              src="/landing/product-evidence/assignment-explanation.jpg"
              alt="PolicyOS employee assignment view showing a USD 10,000 expense approval limit, the winning People Manager Responsibilities policy, its priority, and the evidence that matched"
              label="assignment explanation"
              figure="fig. 01"
              priority
            />
            <div className={styles.heroResultCard}>
              <span>Resolved assignment</span>
              <strong>USD 10,000</strong>
              <div>
                <CheckCircle2 size={16} />
                <p>
                  <b>People Manager Responsibilities</b>
                  Priority 45 · Direct match
                </p>
              </div>
            </div>
          </div>

          <div className={styles.heroFooter}>
            <span>Preview first</span>
            <span>Resolve explicitly</span>
            <span>Explain completely</span>
          </div>
        </section>

        <section id="platform" className={styles.platform} aria-labelledby="platform-title">
          <div className={styles.sectionHeading}>
            <Eyebrow>Why PolicyOS</Eyebrow>
            <h2 id="platform-title">Policy assignment is a system—not a spreadsheet ritual.</h2>
            <p>
              Design the rules once, expose the impact before activation, and give operators a
              durable answer when someone asks why.
            </p>
          </div>
          <div className={styles.pillarGrid}>
            {pillars.map(({ number, icon: Icon, title, copy }) => (
              <article key={number}>
                <div className={styles.pillarTopline}>
                  <span>{number}</span>
                  <Icon size={22} strokeWidth={1.6} />
                </div>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
          <div className={styles.capabilityRail} aria-label="Additional PolicyOS capabilities">
            <span>Groups + inherited context</span>
            <span>Manual overrides</span>
            <span>Versioned changes</span>
            <span>Audit history</span>
            <span>Access governance</span>
          </div>
        </section>

        <section id="workflow" className={styles.workflow} aria-labelledby="workflow-title">
          <div className={styles.workflowHeading}>
            <Eyebrow>Operating model</Eyebrow>
            <h2 id="workflow-title">From field definition to an auditable decision.</h2>
          </div>
          <ol className={styles.workflowSteps}>
            {workflow.map(([verb, title, copy], index) => (
              <li key={verb}>
                <span className={styles.workflowNumber}>0{index + 1}</span>
                <div>
                  <span className={styles.workflowVerb}>{verb}</span>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </div>
                {index < workflow.length - 1 ? (
                  <ArrowRight className={styles.workflowArrow} size={18} aria-hidden="true" />
                ) : (
                  <Check className={styles.workflowArrow} size={18} aria-hidden="true" />
                )}
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.previewSection} aria-labelledby="preview-title">
          <div className={styles.previewCopy}>
            <Eyebrow>Change control</Eyebrow>
            <h2 id="preview-title">Know the blast radius before you save.</h2>
            <p>
              Preview employee, group, and policy changes through the same domain path used to
              commit them. Review changed fields, unchanged outcomes, sources, and conflicts—then
              decide.
            </p>
            <ul>
              <li>
                <Check size={15} /> Real resolver behavior
              </li>
              <li>
                <Check size={15} /> No preview data persisted
              </li>
              <li>
                <Check size={15} /> Field-level before and after
              </li>
            </ul>
          </div>
          <ProductWindow
            src="/landing/product-evidence/change-preview.jpg"
            alt="PolicyOS change preview for Priya Raman showing which assignments would remain the same and which would change before confirmation"
            label="employee change preview"
            figure="fig. 02"
          />
        </section>

        <section
          id="explainability"
          className={styles.explainability}
          aria-labelledby="explainability-title"
        >
          <div className={styles.explainHeading}>
            <Eyebrow inverse>Decision record</Eyebrow>
            <h2 id="explainability-title">“Why?” should have a precise answer.</h2>
            <p>
              PolicyOS stores the decision context with the assignment, so today’s explanation does
              not drift when policies change tomorrow.
            </p>
          </div>
          <div className={styles.explainGrid}>
            <div className={styles.decisionTrace}>
              <div className={styles.traceHeader}>
                <span>Expense Approval Limit</span>
                <span className={styles.traceStatus}>
                  <CheckCircle2 size={13} /> Resolved
                </span>
              </div>
              <strong className={styles.traceValue}>USD 10,000</strong>
              <div className={styles.traceWinner}>
                <span>Winning policy / priority 45</span>
                <strong>People Manager Responsibilities</strong>
                <div>
                  <span>Evidence</span>
                  <b>Is Manager</b>
                  <em>Yes</em>
                </div>
              </div>
              <div className={styles.traceCandidate}>
                <span>Lower-priority candidate</span>
                <strong>Field Operations Readiness</strong>
                <small>USD 2,500 · priority 35</small>
              </div>
              <div className={styles.traceReceipt}>
                <FileClock size={16} /> Explanation snapshot retained with assignment
              </div>
            </div>
            <dl className={styles.questionList}>
              {explanationQuestions.map(([question, answer], index) => (
                <div key={question}>
                  <dt>
                    <span>Q{index + 1}</span> {question}
                  </dt>
                  <dd>{answer}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className={styles.policyProof} aria-labelledby="policy-proof-title">
          <div className={styles.policyProofCopy}>
            <Eyebrow>Policy as a governed change</Eyebrow>
            <h2 id="policy-proof-title">
              Conditions, outputs, priority, version, and reach—in one view.
            </h2>
            <p>
              Review the policy definition beside the population it affects. Date-effective versions
              preserve history while new changes move through preview and activation.
            </p>
            <Link href="/learn/policyos/create-your-first-policy">
              Learn how policy authoring works <ArrowRight size={16} />
            </Link>
          </div>
          <ProductWindow
            src="/landing/product-evidence/policy-impact-version.jpg"
            alt="People Manager Responsibilities policy in PolicyOS showing its manager condition, three provided assignments, effective date, priority, version, and affected population"
            label="policy version + population impact"
            figure="fig. 03"
          />
        </section>

        <section id="governance" className={styles.governance} aria-labelledby="governance-title">
          <div className={styles.governanceHeading}>
            <Eyebrow>Governance built into the path</Eyebrow>
            <h2 id="governance-title">Control who can decide. Preserve what they changed.</h2>
            <p>
              The same authorization and validation boundary applies across the product. Sensitive
              actions add deliberate checkpoints without obscuring routine work.
            </p>
          </div>
          <div className={styles.governanceGrid}>
            <article>
              <ShieldCheck size={22} />
              <span>01 / Access</span>
              <h3>Role-based permissions</h3>
              <p>Scope product actions and employee visibility to the signed-in user.</p>
            </article>
            <article>
              <KeyRound size={22} />
              <span>02 / Identity</span>
              <h3>MFA + reauthentication</h3>
              <p>Add a fresh proof of identity before sensitive account operations.</p>
            </article>
            <article>
              <GitCompareArrows size={22} />
              <span>03 / Change</span>
              <h3>Versioned policy history</h3>
              <p>
                Move policy behavior forward without rewriting the record behind prior outcomes.
              </p>
            </article>
            <article>
              <FileClock size={22} />
              <span>04 / Review</span>
              <h3>Audit + access review</h3>
              <p>Investigate recorded changes and surface privileged or stale access for review.</p>
            </article>
          </div>
          <div className={styles.governanceFooter}>
            <div>
              <LockKeyhole size={18} />
              <span>Preview-before-commit safeguards</span>
            </div>
            <div>
              <CircleAlert size={18} />
              <span>Explicit conflicts, not silent tie-breaks</span>
            </div>
            <div>
              <Users size={18} />
              <span>User-bound authorization</span>
            </div>
          </div>
        </section>

        <section className={styles.finalCta} aria-labelledby="cta-title">
          <div>
            <Eyebrow inverse>Ready to make policy operational?</Eyebrow>
            <h2 id="cta-title">Give every assignment a rule, a reason, and a record.</h2>
          </div>
          <div className={styles.finalCtaActions}>
            <Link href="/signup">
              Get started <ArrowRight size={18} />
            </Link>
            <Link href="/login">Sign in to a workspace</Link>
          </div>
          <Sparkles className={styles.ctaSpark} size={44} aria-hidden="true" />
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerLead}>
          <Brand inverse />
          <p>Workforce policy assignments, resolved and explained.</p>
        </div>
        <div>
          <span>Product</span>
          <a href="#platform">Platform</a>
          <a href="#workflow">How it works</a>
          <a href="#explainability">Explainability</a>
          <a href="#governance">Governance</a>
        </div>
        <div>
          <span>Explore</span>
          <Link href="/learn">Learn PolicyOS</Link>
          <Link href="/signup">Get started</Link>
          <Link href="/login">Sign in</Link>
        </div>
        <div className={styles.footerMeta}>
          <span>PolicyOS</span>
          <span>Deterministic by design.</span>
        </div>
      </footer>
    </div>
  );
}
