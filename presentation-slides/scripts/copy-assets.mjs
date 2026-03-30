import { mkdir, copyFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const repoRoot = resolve(projectRoot, "..");

const copies = [
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "01_all_stages_overview.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "01_all_stages_overview.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "05_b_vs_bplus_flips.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "05_b_vs_bplus_flips.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "06_stageC_risk_committee.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "06_stageC_risk_committee.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "08_llm_nondeterminism.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "08_llm_nondeterminism.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "10_21d_action_dist.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "10_21d_action_dist.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "15_21d_pairwise_discordant_wins.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "15_21d_pairwise_discordant_wins.png"),
  },
  {
    from: resolve(repoRoot, "experiments", "results", "charts_analysis", "16_same130_k10_vs_k21.png"),
    to: resolve(projectRoot, "public", "assets", "charts", "16_same130_k10_vs_k21.png"),
  },
  {
    from: resolve(repoRoot, "..", "documentation", "04_meeting_notes", "images", "screenshot_1_initial_system_activity.png"),
    to: resolve(projectRoot, "public", "assets", "ui", "screenshot_1_initial_system_activity.png"),
  },
  {
    from: resolve(repoRoot, "..", "documentation", "04_meeting_notes", "images", "screenshot_2_graph_and_agents'_summary.png"),
    to: resolve(projectRoot, "public", "assets", "ui", "screenshot_2_graph_and_agents_summary.png"),
  },
];

for (const copy of copies) {
  await mkdir(dirname(copy.to), { recursive: true });
  await copyFile(copy.from, copy.to);
}

console.log(`Synced ${copies.length} presentation assets.`);