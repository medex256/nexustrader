import type { ReactNode } from "react";

type SlideSpec = {
  id: string;
  number: number;
  tag: string;
  content: ReactNode;
};

type FigureProps = {
  src: string;
  alt: string;
  caption: string;
  footer?: string;
  imageClassName?: string;
  kicker?: string;
};

type StatItem = {
  label: string;
  value: string;
};

function Figure({ src, alt, caption, footer, imageClassName, kicker }: FigureProps) {
  return (
    <figure className="figure-card">
      <div className="figure-image-shell">
        <img src={src} alt={alt} className={imageClassName ? `figure-image ${imageClassName}` : "figure-image"} />
      </div>
      <figcaption>
        {kicker ? <small>{kicker}</small> : null}
        <strong>{caption}</strong>
        {footer ? <span>{footer}</span> : null}
      </figcaption>
    </figure>
  );
}

function FigureStats({ items }: { items: StatItem[] }) {
  return (
    <div className="figure-stats-grid">
      {items.map((item) => (
        <div key={`${item.label}-${item.value}`} className="figure-stat-card">
          <strong>{item.value}</strong>
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

function SlideHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="slide-header">
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
    </header>
  );
}

function SectionKicker({ text }: { text: string }) {
  return (
    <div className="summary-kicker slide-kicker">
      <span className="summary-kicker-dot" />
      <span>{text}</span>
    </div>
  );
}

function InsightItem({ title, body, tone = "default" }: { title: string; body: string; tone?: "default" | "accent" | "warn" | "success" }) {
  return (
    <div className={`insight-item insight-${tone}`}>
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function AccentStrip() {
  return (
    <div className="stage-strip" aria-hidden="true">
      <span className="stage-chip stage-a">A</span>
      <span className="stage-arrow">{"->"}</span>
      <span className="stage-chip stage-b">B</span>
      <span className="stage-arrow">{"->"}</span>
      <span className="stage-chip stage-bp">B+</span>
      <span className="stage-arrow">{"->"}</span>
      <span className="stage-chip stage-c">C</span>
      <span className="stage-branch">{"B+ -> D"}</span>
    </div>
  );
}

export const slides: SlideSpec[] = [
  {
    id: "title",
    number: 1,
    tag: "Title",
    content: (
      <section className="slide slide-title">
        <SectionKicker text="31 March FYP presentation" />
        <SlideHeader title="NexusTrader tests which multi-agent trading configurations actually improve decisions." />
        <p className="lead-text">
          A transparent multi-agent decision-support app was built, then used to compare which workflow additions actually help short-horizon forecasting.
        </p>
        <div className="title-footer">
          <div>
            <strong>Madi</strong>
            <span>Department of Electrical Engineering</span>
            <span>Supervisor: add final name before export</span>
          </div>
          <AccentStrip />
        </div>
      </section>
    ),
  },
  {
    id: "journey",
    number: 2,
    tag: "Story",
    content: (
      <section className="slide">
        <SectionKicker text="Project journey" />
        <SlideHeader
          title="NexusTrader began as an explainable multi-agent app, then became a way to test which configurations actually help."
          subtitle="Application first, controlled comparison second."
        />
        <div className="three-card-grid">
          <div className="info-card">
            <h3>1. Build Goal</h3>
            <p>Build an explainable app with usable workflows, visible reasoning, and stage-based configuration.</p>
          </div>
          <div className="info-card">
            <h3>2. What Changed</h3>
            <p>Once the stage ladder worked, the app became a practical way to compare workflow topologies.</p>
          </div>
          <div className="info-card">
            <h3>3. Project Question</h3>
            <p>Which additions improve decisions enough to justify extra cost, complexity, and inconsistency?</p>
          </div>
        </div>
        <div className="question-bar">Which configurations improve decisions enough to be worth keeping?</div>
      </section>
    ),
  },
  {
    id: "architecture",
    number: 3,
    tag: "System",
    content: (
      <section className="slide">
        <SectionKicker text="System overview" />
        <SlideHeader
          title="The system combines a transparent frontend, configurable backend workflows, and a reproducible historical testing pipeline."
          subtitle="Minimal diagram redraw for slide use."
        />
        <div className="pipeline-row">
          <div className="pipeline-box">User / Evaluator</div>
          <div className="pipeline-box emphasis-blue">React / TS Frontend</div>
          <div className="pipeline-box">FastAPI Backend</div>
          <div className="pipeline-box">LangGraph Orchestrator</div>
          <div className="pipeline-box emphasis-purple">Stage Pipeline</div>
        </div>
        <div className="support-row">
          <div className="support-box">Market data and research tools</div>
          <div className="support-box">SQLite archive</div>
          <div className="support-box">ChromaDB memory</div>
        </div>
        <div className="pill-row">
          <span className="metric-pill">FastAPI backend</span>
          <span className="metric-pill">LangGraph orchestration</span>
          <span className="metric-pill">React / TS frontend</span>
          <span className="metric-pill">SQLite archive</span>
          <span className="metric-pill">ChromaDB memory experiment</span>
        </div>
      </section>
    ),
  },
  {
    id: "ladder",
    number: 4,
    tag: "Stages",
    content: (
      <section className="slide">
        <SectionKicker text="Configuration ladder" />
        <SlideHeader
          title="The configuration ladder adds one mechanism at a time so design effects can be isolated."
          subtitle="Minimal visual: stage cards plus short role labels."
        />
        <div className="ladder-row">
          <div className="ladder-stage stage-a"><strong>A</strong><span>baseline decision core</span></div>
          <div className="ladder-stage stage-b"><strong>B</strong><span>better evidence surfacing</span></div>
          <div className="ladder-stage stage-bp"><strong>B+</strong><span>lightweight gating</span></div>
          <div className="ladder-stage stage-c"><strong>C</strong><span>full risk debate</span></div>
        </div>
        <div className="ladder-branch">
          <div className="ladder-stage stage-d"><strong>D</strong><span>memory retrieval test</span></div>
        </div>
        <p className="bottom-note">
          The design logic is bottom-up: add one mechanism, then compare whether it earns its extra complexity.
        </p>
      </section>
    ),
  },
  {
    id: "evaluation",
    number: 5,
    tag: "Method",
    content: (
      <section className="slide">
        <SectionKicker text="Evaluation method" />
        <SlideHeader
          title="Frozen runs and matched-row follow-up let the app's configurations be compared without overclaiming."
          subtitle="Method slide designed as clean process plus metric summary."
        />
        <div className="evaluation-layout">
          <div className="evaluation-flow">
            <div className="flow-step"><strong>Panel</strong><span>5 tickers x 77 dates</span></div>
            <div className="flow-step"><strong>Frozen run</strong><span>Main comparison at k = 10</span></div>
            <div className="flow-step"><strong>Scoring</strong><span>Directional accuracy, hold rate, flip quality</span></div>
            <div className="flow-step"><strong>Follow-up</strong><span>same-row k = 21 on 130 cases</span></div>
          </div>
          <div className="metrics-grid">
            <div className="metrics-card"><strong>5</strong><span>tickers</span></div>
            <div className="metrics-card"><strong>77</strong><span>dates</span></div>
            <div className="metrics-card"><strong>385</strong><span>k=10 cases</span></div>
            <div className="metrics-card"><strong>130</strong><span>same-row k=21</span></div>
          </div>
        </div>
        <div className="warning-box">
          Cross-run gaps are not automatically causal because LLM outputs remain non-deterministic.
        </div>
      </section>
    ),
  },
  {
    id: "k10-results",
    number: 6,
    tag: "Results",
    content: (
      <section className="slide slide-results">
        <SectionKicker text="Main result" />
        <SlideHeader
          title="At k = 10, lightweight risk gating is the strongest refinement and full debate is net negative."
          subtitle="Use the exported chart as evidence, but present the conclusion in the same structured way the product surfaces analysis summaries."
        />
        <div className="results-layout">
          <div className="figure-column">
            <Figure
              src="/assets/charts/01_all_stages_overview.png"
              alt="All stages overview at k equals 10"
              kicker="Figure 1"
              caption="Frozen k = 10 directional-accuracy overview"
              footer="Cropped to the primary panel so the audience sees the stage comparison first, not the full notebook-style export."
              imageClassName="figure-image--left-focus"
            />
            <FigureStats
              items={[
                { label: "Stage A", value: "55.0%" },
                { label: "Stage B", value: "54.3%" },
                { label: "Stage B+", value: "54.52%" },
                { label: "Stage C", value: "51.87%" },
                { label: "Stage D", value: "54.30%" },
              ]}
            />
          </div>
          <div className="analysis-panel">
            <div className="verdict-hero slide-verdict-hero">
              <div className="verdict-badge-wrap">
                <div className="verdict-action hold">k = 10</div>
              </div>
              <div className="verdict-meta">
                <div className="stage-added-label">Primary read</div>
                <h3 className="result-hero-title">B+ is the cleanest short-horizon refinement, while Stage C is the clear negative result.</h3>
                <p className="result-hero-copy">
                  Stage A still has the highest raw directional score at 55.0%, but it almost never abstains. Among the stages that add control layers, B+ is the best-balanced refinement at 54.52%, while Stage C drops to 51.87% and becomes the most conservative stage.
                </p>
              </div>
            </div>
            <div className="insight-stack">
              <InsightItem
                title="Stage A: 55.0% with only 1.3% HOLD"
                body="Strong committed baseline, but it gets that by almost never abstaining."
                tone="default"
              />
              <InsightItem
                title="Stage B+: 54.52%"
                body="Best lightweight refinement among the gated stages, with a modest but defensible improvement over B."
                tone="success"
              />
              <InsightItem
                title="Stage C: 51.87% and 30.39% HOLD"
                body="Adds the heaviest challenge layer, but at k = 10 it becomes too conservative and hurts decision quality."
                tone="warn"
              />
              <InsightItem
                title="Stage D: 54.30%"
                body="Memory returns to the Stage B level, so there is no clean uplift on this frozen short-horizon set."
                tone="accent"
              />
            </div>
            <div className="callout-grid compact-callouts">
              <div className="callout-box accent-green"><strong>B to B+</strong><span>19 helped vs 9 hurt</span></div>
              <div className="callout-box accent-red"><strong>Stage C</strong><span>BLOCK net = -5</span></div>
              <div className="callout-box accent-gold"><strong>Stage D</strong><span>no clean memory uplift</span></div>
            </div>
          </div>
        </div>
        <p className="source-line">Source: NexusTrader frozen k=10 evaluation and matched-row k=21 follow-up; scored with Yahoo Finance prices via yfinance.</p>
      </section>
    ),
  },
  {
    id: "same-row-followup",
    number: 7,
    tag: "Follow-up",
    content: (
      <section className="slide slide-results">
        <SectionKicker text="Matched-row follow-up" />
        <SlideHeader
          title="On the same rows, Stage C improves at k = 21, suggesting horizon sensitivity rather than a universally bad design."
          subtitle="Same-row evidence should read like a controlled comparison, not like another raw chart dump."
        />
        <div className="results-layout">
          <div className="figure-column">
            <Figure
              src="/assets/charts/16_same130_k10_vs_k21.png"
              alt="Same row comparison between k equals 10 and k equals 21"
              kicker="Figure 2"
              caption="Matched-row directional accuracy at k = 10 vs k = 21"
              footer="Again cropped to the primary panel so the stage-to-stage horizon shift reads clearly from a distance."
              imageClassName="figure-image--left-focus"
            />
            <FigureStats
              items={[
                { label: "B+", value: "58.51% -> 56.25%" },
                { label: "C", value: "52.27% -> 59.80%" },
                { label: "D", value: "57.14% -> 57.41%" },
              ]}
            />
          </div>
          <div className="analysis-panel">
            <div className="verdict-hero slide-verdict-hero">
              <div className="verdict-badge-wrap">
                <div className="verdict-action buy">k = 21</div>
              </div>
              <div className="verdict-meta">
                <div className="stage-added-label">Primary read</div>
                <h3 className="result-hero-title">Stage C improves materially at the longer horizon, but the right claim is still cautious.</h3>
                <p className="result-hero-copy">
                  On the same 130 rows, Stage C rises from 52.27% to 59.80%. B+ softens slightly, and Stage D remains broadly flat. That pattern suggests horizon sensitivity, but the disagreement evidence is still too close to call it final proof.
                </p>
              </div>
            </div>
            <div className="insight-stack">
              <InsightItem
                title="Stage C: 52.27% to 59.80%"
                body="This is the strongest directional shift in the figure and is the main reason the longer-horizon follow-up matters."
                tone="success"
              />
              <InsightItem
                title="B+: 58.51% to 56.25%"
                body="The lightweight gate is slightly weaker at the longer horizon on the same matched rows."
                tone="default"
              />
              <InsightItem
                title="D: 57.14% to 57.41%"
                body="Memory stays roughly flat, so the longer-horizon panel still does not justify a strong memory-uplift claim."
                tone="accent"
              />
              <InsightItem
                title="Interpretation stays cautious"
                body="Pairwise discordant wins remain close, so treat this as suggestive horizon sensitivity rather than a definitive winner."
                tone="warn"
              />
            </div>
            <div className="callout-grid compact-callouts">
              <div className="callout-box accent-purple"><strong>Stage C shift</strong><span>52.27% to 59.80%</span></div>
              <div className="callout-box"><strong>B+ softens</strong><span>58.51% to 56.25%</span></div>
              <div className="callout-box"><strong>D stays flat</strong><span>57.14% to 57.41%</span></div>
            </div>
          </div>
        </div>
        <p className="source-line">Source: NexusTrader frozen k=10 evaluation and matched-row k=21 follow-up; scored with Yahoo Finance prices via yfinance.</p>
      </section>
    ),
  },
  {
    id: "ui",
    number: 8,
    tag: "UI",
    content: (
      <section className="slide">
        <SectionKicker text="Explainability UI" />
        <SlideHeader
          title="The interface makes the configurable workflow and final recommendation easy to inspect."
          subtitle="Static walkthrough, no live-demo dependency."
        />
        <div className="ui-grid">
          <Figure
            src="/assets/ui/screenshot_1_initial_system_activity.png"
            alt="Initial system activity screenshot"
            caption="Choose stage and input"
          />
          <Figure
            src="/assets/ui/screenshot_1_initial_system_activity.png"
            alt="Live analysis screenshot"
            caption="Inspect agent reasoning as it runs"
          />
          <Figure
            src="/assets/ui/screenshot_2_graph_and_agents_summary.png"
            alt="Final recommendation screenshot"
            caption="Review final recommendation and archived trace"
          />
        </div>
      </section>
    ),
  },
  {
    id: "conclusion",
    number: 9,
    tag: "Conclusion",
    content: (
      <section className="slide">
        <SectionKicker text="Conclusion" />
        <SlideHeader
          title="The main contribution is a transparent application plus a controlled comparison of workflow configurations."
          subtitle="Minimal closing slide with three tiles and a single bottom-line claim."
        />
        <div className="three-card-grid">
          <div className="info-card"><h3>Usable explainable prototype</h3><p>Full-stack app with stage-specific workflow inspection and archived run traces.</p></div>
          <div className="info-card"><h3>B+ is the cleanest short-horizon refinement</h3><p>At k = 10, B+ keeps the best trade-off between evidence quality and added complexity.</p></div>
          <div className="info-card"><h3>Stage C is horizon-sensitive; Stage D remains mixed</h3><p>Stage C improves at k = 21 on the same rows, while memory remains inconclusive.</p></div>
        </div>
        <div className="metric-pills-large">
          <span className="metric-pill">B+ at k=10: 54.52%</span>
          <span className="metric-pill">Stage C same-row: 52.27% to 59.80%</span>
          <span className="metric-pill">Stage D: no clean memory uplift</span>
        </div>
        <div className="question-bar">Topology choice matters more than simply adding more agents.</div>
      </section>
    ),
  },
  {
    id: "appendix-bplus",
    number: 10,
    tag: "Appendix",
    content: (
      <section className="slide slide-results">
        <SlideHeader
          title="Appendix A — Why B+ is better than B"
          subtitle="Use this when someone asks why B+ is still worth keeping if the headline gain is small."
        />
        <div className="results-layout">
          <div className="figure-column">
            <Figure
              src="/assets/charts/05_b_vs_bplus_flips.png"
              alt="B versus B plus flip analysis"
              kicker="Appendix Figure A"
              caption="Flip analysis for B vs B+"
              footer="Useful as a support figure when someone asks why B+ is worth keeping despite a small headline gain."
            />
            <FigureStats
              items={[
                { label: "helped", value: "19" },
                { label: "hurt", value: "9" },
                { label: "neutral", value: "37" },
                { label: "net", value: "+10" },
              ]}
            />
          </div>
          <div className="analysis-panel">
            <div className="analysis-block">
              <h3>What the figure says</h3>
              <p>
                Even though the headline gain over B is small, B+ changes the answer in a directionally useful way more often than it harms it.
                Across 65 decision flips, B+ helps 19 times and hurts only 9 times, giving a net positive effect of +10.
              </p>
            </div>
          </div>
        </div>
      </section>
    ),
  },
  {
    id: "appendix-stagec",
    number: 11,
    tag: "Appendix",
    content: (
      <section className="slide slide-results">
        <SlideHeader
          title="Appendix B — Why Stage C is negative at k = 10"
          subtitle="Within-run BLOCK analysis, not a noisy cross-run accuracy comparison."
        />
        <div className="results-layout">
          <div className="figure-column">
            <Figure
              src="/assets/charts/06_stageC_risk_committee.png"
              alt="Stage C risk committee figure"
              kicker="Appendix Figure B"
              caption="Stage C risk-committee BLOCK analysis"
              footer="Within-run mechanism evidence, not a noisy cross-run claim."
            />
            <FigureStats
              items={[
                { label: "BLOCK rows", value: "35" },
                { label: "helped", value: "6" },
                { label: "hurt", value: "11" },
                { label: "net", value: "-5" },
              ]}
            />
          </div>
          <div className="analysis-panel">
            <div className="analysis-block">
              <h3>What the figure says</h3>
              <p>
                The debate only blocks 35 rows, but when it does, it blocks more correct manager calls than incorrect ones.
                That gives 11 hurts versus 6 helps, with 18 neutral, so the net effect is -5.
              </p>
            </div>
          </div>
        </div>
      </section>
    ),
  },
];