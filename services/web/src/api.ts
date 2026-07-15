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
  description: string;
  source_format: string;
  source_type: string;
  overall_score: number | null;
  categories: Category[];
  task_group: string | null;
  updated_at: string;
}

export interface TaskGroup {
  key: string;
  count: number;
  avg_overall: number | null;
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
  references: { path: string; content: string }[];
  section_headings: string[];
  version_no: number;
  latest_evaluation: Evaluation | null;
  similar: SimilarSkill[];
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
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
  createSkill: (payload: SkillCreate) =>
    request<SkillDetail>("/skills", { method: "POST", body: JSON.stringify(payload) }),
  deleteSkill: (id: number) => request<void>(`/skills/${id}`, { method: "DELETE" }),
  listCategories: () => request<CategoryInfo[]>("/categories"),
  listTaskGroups: () => request<TaskGroup[]>("/task-groups"),
  search: (q: string) => request<SearchHit[]>(`/search?q=${encodeURIComponent(q)}`),
  stats: () => request<Stats>("/stats"),
  rubric: () => request<Rubric>("/rubric"),
};
