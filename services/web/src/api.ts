// Typed client for the SkillHub API. Uses relative /api URLs so the same build works behind
// the Vite dev proxy and the production nginx proxy.

const BASE = "/api";

export interface Category {
  key: string;
  label: string;
  confidence?: number | null;
}

export interface CategoryInfo {
  key: string;
  label: string;
  description: string;
  skill_count: number;
}

export interface Evaluation {
  model: string;
  rubric_version: string;
  scores: Record<string, number>;
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  rationale: string;
  created_at: string;
}

export interface SkillSummary {
  id: number;
  name: string;
  author: string | null;
  uploaded_by: string | null;
  description: string;
  source_format: string;
  source_type: string;
  overall_score: number | null;
  rubric_version: string | null;
  categories: Category[];
  task_group: string | null;
  updated_at: string;
  // Empirical headline from the sandbox-trial matrix (0..1): the best (skill, model)
  // effectiveness across all recorded trials — judge-panel graded, gated by the objective
  // scorecard. null if the skill has never been trialed. This is a different, more accurate
  // signal than the static rubric `overall_score` above.
  best_effectiveness: number | null;
  best_effectiveness_model: string | null;
}

export interface SkillVersionInfo {
  version_no: number;
  author: string | null;
  created_at: string;
}

export interface Recommendation {
  id: number;
  kind: string;
  title: string;
  rationale: string;
  scope: string | null;
  targets: string[];
  suggested_action: string;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimilarSkill {
  id: number;
  name: string;
  author: string | null;
  similarity: number;
  overall_score: number | null;
}

export interface SkillDetail extends SkillSummary {
  trigger_text: string | null;
  body_md: string;
  // Full canonical SKILL.md (frontmatter + body), ready to install into Claude Code.
  skill_md: string;
  references: { path: string; content: string }[];
  section_headings: string[];
  version_no: number;
  contributors: string[];
  versions: SkillVersionInfo[];
  latest_evaluation: Evaluation | null;
  similar: SimilarSkill[];
  similar_warning: { skill_id: number; name: string; similarity: number } | null;
}

export interface SearchHit {
  skill: SkillSummary;
  similarity: number | null;
}

export interface Stats {
  total: number;
  evaluated: number;
  avg_overall: number | null;
  by_category: { key: string; label: string; count: number }[];
  top: { id: number; name: string; overall: number }[];
}

export interface SkillCreate {
  content: string;
  author?: string | null;
  references?: { path: string; content: string }[];
  source_format?: string;
}

export interface Health {
  status: string;
  rubric_version?: string;
}

export interface Me {
  authenticated: boolean;
  reads_require_auth?: boolean;
  id?: number;
  name?: string;
  email?: string | null;
  role?: string;
  can_upload?: boolean;
  can_evaluate?: boolean;
  is_admin?: boolean;
  is_reviewer?: boolean;
}

// --- Task Review context ---
export interface ReviewEvent {
  id: number;
  kind: string;
  author: string | null;
  verdict: string | null;
  body: string;
  created_at: string;
}

export interface ReviewSummary {
  id: number;
  task_ref: string;
  title: string;
  branch: string | null;
  status: string;
  author: string | null;
  reviewer: string | null;
  updated_at: string;
}

export interface ReviewDetail extends ReviewSummary {
  commit_shas: string[];
  summary: string;
  files: string[];
  verified_notes: string;
  created_at: string;
  events: ReviewEvent[];
}

export interface RubricCategory {
  key: string;
  label: string;
  description: string;
}

export interface Rubric {
  rubric_version: string;
  instructions: string;
  dimensions: { key: string; description: string }[];
  evaluation_schema: Record<string, unknown>;
  categories: RubricCategory[];
  weights: Record<string, number>;
  calibration: { band: string; label: string; meaning: string }[];
  categorization_rules: string;
  selection_strategy: string;
  synthesis_strategy: string;
  synthesis_algorithm: { step: string; detail: string }[];
  synthesis_prompt: string;
}

// --- Sandbox trial notebook (one per skill) ---
export interface TrialEntry {
  label: string;
  skill_name?: string;
  skill_version?: string;
  passed: string[];
  failed: string[];
  score: string;
}

export interface TrialSummary {
  scenario?: string;
  task_group?: string;
  created_at?: string;
  entries?: TrialEntry[];
}

export interface NotebookCell {
  cell_type: string;
  source: string | string[];
  outputs?: { output_type: string; name?: string; text?: string | string[] }[];
}

export interface SkillNotebook {
  skill_id: number;
  model: string;
  scenario: string;
  task_group: string | null;
  notebook: { cells?: NotebookCell[]; [k: string]: unknown };
  summary: TrialSummary;
  effectiveness: number | null;
  // The two components behind effectiveness: the judge panel's median grade (0..10) and the
  // objective keyword pass-rate (0..1) that caps it. ``dimensions`` = panel-median per criterion;
  // ``panel`` = the individual blind judge votes. Null for older, ungraded trials.
  result_grade: number | null;
  objective_rate: number | null;
  dimensions: Record<string, number> | null;
  panel: JudgeVote[] | null;
  tested_version_no: number | null;
  stale: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// One blind judge's vote on a trial artifact.
export interface JudgeVote {
  judge: string;
  overall: number;
  dimensions?: Record<string, number>;
  note?: string;
}

// One row of the effectiveness-by-model matrix (no heavy notebook payload).
export interface NotebookModelSummary {
  model: string;
  scenario: string;
  effectiveness: number | null;
  result_grade: number | null;
  objective_rate: number | null;
  dimensions: Record<string, number> | null;
  stale: boolean;
  created_by: string | null;
  created_at: string | null;
}

export interface SkillFit {
  skill_id: number;
  best_model: string | null;
  entries: NotebookModelSummary[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    // Send the session cookie so logged-in writes/identity work (same-origin in dev & prod).
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  listSkills: (search?: string, category?: string) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (category) params.set("category", category);
    const qs = params.toString();
    return request<SkillSummary[]>(`/skills${qs ? `?${qs}` : ""}`);
  },
  getSkill: (id: number) => request<SkillDetail>(`/skills/${id}`),
  // A sandbox-trial notebook for a skill; ``model`` selects the executing model's trial (omitted =
  // best-scoring model). null when no trial has been recorded (404).
  getSkillNotebook: async (id: number, model?: string): Promise<SkillNotebook | null> => {
    const qs = model ? `?model=${encodeURIComponent(model)}` : "";
    try {
      return await request<SkillNotebook>(`/skills/${id}/notebook${qs}`);
    } catch (err) {
      if (err instanceof Error && err.message.startsWith("404")) return null;
      throw err;
    }
  },
  // The skill's effectiveness-by-model matrix (best_model + per-model score; empty entries = none).
  getSkillFit: (id: number) => request<SkillFit>(`/skills/${id}/notebooks`),
  createSkill: (payload: SkillCreate) =>
    request<SkillDetail>("/skills", { method: "POST", body: JSON.stringify(payload) }),
  deleteSkill: (id: number) => request<void>(`/skills/${id}`, { method: "DELETE" }),
  listCategories: () => request<CategoryInfo[]>("/categories"),
  listRecommendations: () => request<Recommendation[]>("/recommendations"),
  search: (q: string) => request<SearchHit[]>(`/search?q=${encodeURIComponent(q)}`),
  stats: () => request<Stats>("/stats"),
  rubric: () => request<Rubric>("/rubric"),
  updateRubricWeights: (weights: Record<string, number>) =>
    request<{ weights: Record<string, number>; rescored: number }>("/rubric/weights", {
      method: "PUT",
      body: JSON.stringify({ weights }),
    }),
  // --- reviews ---
  listReviews: (opts?: { status?: string; mine?: boolean; queue?: boolean }) => {
    const params = new URLSearchParams();
    if (opts?.status) params.set("status", opts.status);
    if (opts?.mine) params.set("mine", "true");
    if (opts?.queue) params.set("queue", "true");
    const qs = params.toString();
    return request<ReviewSummary[]>(`/reviews${qs ? `?${qs}` : ""}`);
  },
  getReview: (id: number) => request<ReviewDetail>(`/reviews/${id}`),
  // --- auth ---
  me: () => request<Me>("/auth/me"),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  deviceApprove: (userCode: string) =>
    request<{ ok: boolean; client_label: string | null }>("/auth/device/approve", {
      method: "POST",
      body: JSON.stringify({ user_code: userCode }),
    }),
};
