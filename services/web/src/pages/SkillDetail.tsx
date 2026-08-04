import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Container,
  CopyButton,
  Divider,
  Grid,
  Group,
  List,
  Loader,
  Paper,
  Progress,
  Spoiler,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { NotebookCell, SkillFit, SkillNotebook, TrialEntry } from "../api";
import { ScoreBadge, ScoreBreakdown } from "../components/Score";
import { useI18n } from "../i18n";
import { KIND_COLOR } from "./Recommendations";

export default function SkillDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const skillId = Number(id);

  const { data: skill, isLoading } = useQuery({
    queryKey: ["skill", skillId],
    queryFn: () => api.getSkill(skillId),
  });
  const { data: allRecs } = useQuery({
    queryKey: ["recommendations"],
    queryFn: api.listRecommendations,
  });
  // Effectiveness-by-model matrix; the viewer defaults to the best model, overridable by clicking.
  const { data: fit } = useQuery({
    queryKey: ["skill-fit", skillId],
    queryFn: () => api.getSkillFit(skillId),
  });
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const activeModel = selectedModel ?? fit?.best_model ?? null;
  const { data: notebook } = useQuery({
    queryKey: ["skill-notebook", skillId, activeModel],
    queryFn: () => api.getSkillNotebook(skillId, activeModel ?? undefined),
    enabled: !!activeModel,
  });

  if (isLoading) {
    return (
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    );
  }
  if (!skill) {
    return (
      <Container>
        <Alert color="red">{t("detail.notFound")}</Alert>
      </Container>
    );
  }

  const evalr = skill.latest_evaluation;
  const installPhrase = t("detail.installPhrase", { name: skill.name });

  // Open recommendations that apply to THIS skill: it is a named target, or the scope matches the
  // skill's name / task_group / one of its categories.
  const catKeys = new Set(skill.categories.map((c) => c.key));
  const improvements = (allRecs ?? []).filter(
    (r) =>
      (r.status === "proposed" || r.status === "accepted") &&
      (r.targets.includes(skill.name) ||
        r.scope === skill.name ||
        (skill.task_group != null && r.scope === skill.task_group) ||
        (r.scope != null && catKeys.has(r.scope))),
  );
  // Same "improve" highlight the catalog card shows, at a glance in the header — sourced from
  // the skill's own field (server-computed, same data as the catalog) rather than the client-side
  // `improvements` match below, so it doesn't depend on a second, independently-failable fetch.
  const openImproveCount = skill.open_improve_count;

  return (
    <Container size="xl">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap="sm">
              <Title order={2}>{skill.name}</Title>
              <ScoreBadge value={skill.overall_score} />
              {openImproveCount > 0 && (
                <Badge color={KIND_COLOR.improve} variant="filled">
                  {t("catalog.openImprove", { n: openImproveCount })}
                </Badge>
              )}
            </Group>
            <Text c="dimmed" size="sm">
              {t("detail.meta", {
                author: skill.author ?? t("catalog.unknownAuthor"),
                version: skill.version_no,
                format: skill.source_format,
              })}
            </Text>
            <Group gap={4} mt="xs">
              {skill.categories.map((c) => (
                <Badge key={c.key} variant="light">
                  {c.label}
                  {c.confidence != null && ` ${(c.confidence * 100).toFixed(0)}%`}
                </Badge>
              ))}
            </Group>
          </div>
        </Group>

        <Grid>
          {/* Left: content */}
          <Grid.Col span={{ base: 12, md: 8 }}>
            {skill.trigger_text && (
              <Alert color="indigo" variant="light" title={t("detail.whenToUse")} mb="md">
                {skill.trigger_text}
              </Alert>
            )}

            {/* The empirical per-model trial leads — it's the primary signal now. */}
            <SandboxTrial
              fit={fit}
              notebook={notebook}
              activeModel={activeModel}
              onSelectModel={setSelectedModel}
            />

            {/* SKILL.md body — reduced to a preview (Spoiler) so it no longer dominates. */}
            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="xs">
                {t("detail.bodyTitle")}
              </Text>
              <Spoiler
                maxHeight={180}
                showLabel={t("detail.bodyShowMore")}
                hideLabel={t("detail.bodyShowLess")}
              >
                <Paper
                  p="sm"
                  bg="var(--mantine-color-default-hover)"
                  style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13 }}
                >
                  {skill.body_md}
                </Paper>
              </Spoiler>
            </Card>

            {skill.references.length > 0 && (
              <Card withBorder radius="md" padding="md" mt="md">
                <Text fw={600} mb="xs">
                  {t("detail.references")}
                </Text>
                <Accordion variant="contained">
                  {skill.references.map((ref) => (
                    <Accordion.Item key={ref.path} value={ref.path}>
                      <Accordion.Control>{ref.path}</Accordion.Control>
                      <Accordion.Panel>
                        <Paper
                          p="sm"
                          style={{
                            whiteSpace: "pre-wrap",
                            fontFamily: "monospace",
                            fontSize: 12,
                          }}
                        >
                          {ref.content}
                        </Paper>
                      </Accordion.Panel>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Card>
            )}
          </Grid.Col>

          {/* Right: install + evaluation + similar */}
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card withBorder radius="md" padding="md" mb="md">
              <Group justify="space-between" align="center" mb="xs" wrap="nowrap">
                <Text fw={600}>{t("detail.installTitle")}</Text>
                <CopyButton value={installPhrase}>
                  {({ copied, copy }) => (
                    <Button
                      size="compact-xs"
                      variant="light"
                      color={copied ? "teal" : "gray"}
                      onClick={copy}
                    >
                      {copied ? t("common.copied") : t("common.copy")}
                    </Button>
                  )}
                </CopyButton>
              </Group>
              <Text size="sm" c="dimmed" mb={6}>
                {t("detail.installHint")}
              </Text>
              <Code block style={{ whiteSpace: "pre-wrap" }}>
                {installPhrase}
              </Code>
              <Text size="xs" c="dimmed" mt={6}>
                {t("detail.installNote", { name: skill.name })}
              </Text>
            </Card>

            {improvements.length > 0 && (
              <Card
                withBorder
                radius="md"
                padding="md"
                mb="md"
                style={{ borderColor: "var(--mantine-color-indigo-4)" }}
              >
                <Text fw={600} mb="sm">
                  ✨ {t("detail.improvements", { count: improvements.length })}
                </Text>
                <Stack gap="sm">
                  {improvements.map((r) => (
                    <Paper key={r.id} withBorder radius="sm" p="sm">
                      <Group gap="xs" mb={4} wrap="nowrap">
                        <Badge color={KIND_COLOR[r.kind] ?? "gray"} variant="filled" size="sm">
                          {r.kind}
                        </Badge>
                        <Text size="sm" fw={600}>
                          {r.title}
                        </Text>
                      </Group>
                      <Text size="xs" c="dimmed" mb={r.suggested_action ? 6 : 0}>
                        {r.rationale}
                      </Text>
                      {r.suggested_action && (
                        <>
                          <Group justify="space-between" align="center" mb={4}>
                            <Text size="xs" c="dimmed">
                              {t("rec.runThis")}
                            </Text>
                            <CopyButton value={r.suggested_action}>
                              {({ copied, copy }) => (
                                <Button
                                  size="compact-xs"
                                  variant="light"
                                  color={copied ? "teal" : "gray"}
                                  onClick={copy}
                                >
                                  {copied ? t("common.copied") : t("common.copy")}
                                </Button>
                              )}
                            </CopyButton>
                          </Group>
                          <Code block style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                            {r.suggested_action}
                          </Code>
                        </>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Card>
            )}

            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb="sm">
                {t("detail.qualityEval")}
              </Text>
              {evalr ? (
                <Stack gap="sm">
                  <ScoreBreakdown scores={evalr.scores} />
                  <Divider />
                  {evalr.strengths.length > 0 && (
                    <div>
                      <Text size="sm" fw={600} c="teal">
                        {t("detail.strengths")}
                      </Text>
                      <List size="sm">
                        {evalr.strengths.map((s, i) => (
                          <List.Item key={i}>{s}</List.Item>
                        ))}
                      </List>
                    </div>
                  )}
                  {evalr.weaknesses.length > 0 && (
                    <div>
                      <Text size="sm" fw={600} c="orange">
                        {t("detail.weaknesses")}
                      </Text>
                      <List size="sm">
                        {evalr.weaknesses.map((w, i) => (
                          <List.Item key={i}>{w}</List.Item>
                        ))}
                      </List>
                    </div>
                  )}
                  {evalr.rationale && (
                    <Text size="sm" c="dimmed" fs="italic">
                      {evalr.rationale}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed">
                    {t("detail.evalMeta", {
                      model: evalr.model,
                      version: evalr.rubric_version,
                    })}
                  </Text>
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  {t("detail.notEvaluated")}
                </Text>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="sm">
                {t("detail.similar")}
              </Text>
              {skill.similar.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("detail.noNeighbours")}
                </Text>
              ) : (
                <Stack gap="xs">
                  {skill.similar.map((s) => (
                    <Group key={s.id} justify="space-between">
                      <Anchor component={Link} to={`/skills/${s.id}`} size="sm">
                        {s.name}
                      </Anchor>
                      <Badge variant="light" size="sm">
                        {(s.similarity * 100).toFixed(0)}%
                      </Badge>
                    </Group>
                  ))}
                </Stack>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="sm">
                {t("detail.versionHistory")}
              </Text>
              {skill.uploaded_by && (
                <Text size="sm" c="dimmed" mb="xs">
                  {t("detail.updatedBy", { who: skill.uploaded_by })}
                </Text>
              )}
              {skill.contributors.length > 0 && (
                <>
                  <Text size="xs" c="dimmed" mb={4}>
                    {t("detail.contributors")}
                  </Text>
                  <Group gap={4} mb="sm">
                    {skill.contributors.map((c) => (
                      <Badge key={c} variant="light" size="sm">
                        {c}
                      </Badge>
                    ))}
                  </Group>
                </>
              )}
              <Stack gap={4}>
                {skill.versions.map((v) => (
                  <Group key={v.version_no} justify="space-between" wrap="nowrap">
                    <Text size="sm">
                      v{v.version_no} · {v.author ?? t("detail.unknownAuthor")}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {new Date(v.created_at).toLocaleDateString()}
                    </Text>
                  </Group>
                ))}
              </Stack>
            </Card>
          </Grid.Col>
        </Grid>
      </Stack>
    </Container>
  );
}

// --- Sandbox trial (one notebook per skill) --------------------------------------------------

function cellText(src: string | string[] | undefined): string {
  return Array.isArray(src) ? src.join("") : (src ?? "");
}

function scoreColor(entry: TrialEntry): string {
  const [a, b] = entry.score.split("/").map(Number);
  if (!b) return "gray";
  const ratio = a / b;
  return ratio >= 0.999 ? "teal" : ratio >= 0.5 ? "yellow" : "red";
}

// Inline **bold** / `code` → React nodes (never raw HTML → no XSS).
function inlineMd(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) nodes.push(<strong key={`${keyBase}-b${i}`}>{tok.slice(2, -2)}</strong>);
    else nodes.push(<Code key={`${keyBase}-c${i}`}>{tok.slice(1, -1)}</Code>);
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// A minimal, safe markdown renderer for notebook markdown cells: headings, lists, paragraphs.
function Markdown({ src }: { src: string }) {
  const lines = src.split("\n");
  const blocks: ReactNode[] = [];
  let list: ReactNode[] = [];
  const flush = (k: string) => {
    if (list.length) {
      blocks.push(
        <List key={`l${k}`} size="sm" spacing={2} withPadding>
          {list}
        </List>,
      );
      list = [];
    }
  };
  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const heading = /^(#{1,4})\s+(.*)/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)/.exec(line);
    const ordered = /^\s*\d+\.\s+(.*)/.exec(line);
    if (heading) {
      flush(`${idx}`);
      const lvl = heading[1].length;
      blocks.push(
        <Text key={idx} fw={700} size={lvl <= 1 ? "lg" : lvl === 2 ? "md" : "sm"} mt={blocks.length ? "xs" : 0}>
          {inlineMd(heading[2], `h${idx}`)}
        </Text>,
      );
    } else if (bullet || ordered) {
      const content = bullet ? bullet[1] : ordered![1];
      list.push(<List.Item key={idx}>{inlineMd(content, `i${idx}`)}</List.Item>);
    } else if (line === "") {
      flush(`${idx}`);
    } else {
      flush(`${idx}`);
      blocks.push(
        <Text key={idx} size="sm">
          {inlineMd(line, `p${idx}`)}
        </Text>,
      );
    }
  });
  flush("end");
  return <Stack gap={4}>{blocks}</Stack>;
}

function Gutter({ label, color }: { label: string; color: string }) {
  return (
    <Text ff="monospace" fw={700} size="10px" c={color} style={{ width: 34, textAlign: "right", flexShrink: 0, paddingTop: 3 }}>
      {label}
    </Text>
  );
}

const MONO_BLOCK = { flex: 1, minWidth: 0, whiteSpace: "pre" as const, overflowX: "auto" as const, fontSize: 12 };

// Offer the raw notebook as a downloadable .ipynb so anyone can grab the exact file and run it in
// Jupyter / VS Code. Built client-side from the stored notebook JSON (no server round-trip).
function downloadIpynb(filename: string, notebook: unknown): void {
  const blob = new Blob([JSON.stringify(notebook, null, 1)], { type: "application/x-ipynb+json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function NotebookCells({ cells }: { cells: NotebookCell[] }) {
  return (
    <Stack gap="sm">
      {cells.map((cell, i) => {
        const src = cellText(cell.source);
        if (cell.cell_type === "markdown") {
          return (
            <Group key={i} align="flex-start" gap="sm" wrap="nowrap">
              <Gutter label="MD" color="dimmed" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Markdown src={src} />
              </div>
            </Group>
          );
        }
        return (
          <Stack key={i} gap={4}>
            <Group align="flex-start" gap="sm" wrap="nowrap">
              <Gutter label="IN" color="blue" />
              <Code block style={MONO_BLOCK}>
                {src}
              </Code>
            </Group>
            {(cell.outputs ?? []).map((o, j) => (
              <Group key={j} align="flex-start" gap="sm" wrap="nowrap">
                <Gutter label="OUT" color="teal" />
                <Code block style={{ ...MONO_BLOCK, background: "var(--mantine-color-default)" }}>
                  {cellText(o.text)}
                </Code>
              </Group>
            ))}
          </Stack>
        );
      })}
    </Stack>
  );
}

function effColor(v: number | null | undefined): string {
  if (v == null) return "gray";
  if (v >= 0.8) return "teal";
  if (v >= 0.5) return "yellow";
  return "red";
}

// Short labels for the judge-panel dimensions (technical, shown as-is in both locales).
const DIM_SHORT: Record<string, string> = {
  completeness: "compl",
  correctness: "correct",
  scope_discipline: "scope",
  process_fidelity: "process",
  clarity: "clarity",
};

// The panel-median grade per criterion; the weakest (and genuinely low) one is flagged red.
function DimBreakdown({ dims }: { dims: Record<string, number> | null | undefined }) {
  if (!dims) return null;
  const keys = Object.keys(DIM_SHORT).filter((k) => k in dims);
  if (keys.length === 0) return null;
  const min = Math.min(...keys.map((k) => dims[k]));
  return (
    <Group gap={8} wrap="wrap" mt={4}>
      {keys.map((k) => {
        const v = dims[k];
        const weak = v === min && v < 7;
        return (
          <Text key={k} fz={10} ff="monospace" c={weak ? "red" : "dimmed"} fw={weak ? 700 : 400}>
            {DIM_SHORT[k]} {v}
          </Text>
        );
      })}
    </Group>
  );
}

function ModelMatrix({
  fit,
  activeModel,
  onSelectModel,
}: {
  fit: SkillFit;
  activeModel: string | null;
  onSelectModel: (m: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div>
      <Text size="sm" fw={600} mb={2}>
        {t("trial.byModel")}
      </Text>
      <Text fz={11} c="dimmed" mb={6}>
        {t("trial.byModelHint")}
      </Text>
      <Stack gap={6}>
        {fit.entries.map((e) => {
          const pct = e.effectiveness != null ? Math.round(e.effectiveness * 100) : null;
          const gatePct = e.objective_rate != null ? Math.round(e.objective_rate * 100) : null;
          const active = e.model === activeModel;
          return (
            <Paper
              key={e.model}
              withBorder
              radius="sm"
              p="xs"
              onClick={() => onSelectModel(e.model)}
              style={{
                cursor: "pointer",
                borderColor: active ? "var(--mantine-color-blue-5)" : undefined,
                background: active ? "var(--mantine-color-blue-light)" : undefined,
              }}
            >
              <Group justify="space-between" wrap="nowrap" gap="sm" mb={4}>
                <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                  <Text ff="monospace" size="sm" fw={active ? 700 : 500} truncate>
                    {e.model}
                  </Text>
                  {e.model === fit.best_model && (
                    <Badge size="xs" color="blue" variant="light">
                      {t("trial.best")}
                    </Badge>
                  )}
                  {e.stale && (
                    <Badge size="xs" color="orange" variant="light">
                      {t("trial.stale")}
                    </Badge>
                  )}
                </Group>
                {e.result_grade != null ? (
                  <Text size="sm" ff="monospace" fw={700} c={effColor(e.result_grade / 10)}>
                    {e.result_grade.toFixed(1)}
                    <Text span fz={10} c="dimmed">
                      {" "}
                      / 10
                    </Text>
                  </Text>
                ) : (
                  <Text size="sm" ff="monospace" fw={700} c={effColor(e.effectiveness)}>
                    {pct != null ? `${pct}%` : "—"}
                  </Text>
                )}
              </Group>
              <Group gap={8} wrap="nowrap">
                <Progress
                  value={pct ?? 0}
                  color={effColor(e.effectiveness)}
                  size="sm"
                  style={{ flex: 1 }}
                />
                {gatePct != null && (
                  <Text fz={10} ff="monospace" c="dimmed" w={62} ta="right">
                    {t("trial.gateLabel", { v: String(gatePct) })}
                  </Text>
                )}
              </Group>
              <DimBreakdown dims={e.dimensions} />
            </Paper>
          );
        })}
      </Stack>
    </div>
  );
}

// The individual blind judge votes behind the panel-median grade (each judge's overall + note).
function JudgePanel({ notebook }: { notebook: SkillNotebook }) {
  const { t } = useI18n();
  const panel = notebook.panel;
  if (!panel || panel.length === 0) return null;
  const grade = notebook.result_grade;
  return (
    <div>
      <Text size="sm" fw={600} mb={2}>
        {t("trial.panel")}
      </Text>
      <Text fz={11} c="dimmed" mb={6}>
        {t("trial.panelHint", { grade: grade != null ? grade.toFixed(1) : "—", n: String(panel.length) })}
      </Text>
      {notebook.dimensions && <DimBreakdown dims={notebook.dimensions} />}
      <Stack gap={6} mt={6}>
        {panel.map((v, i) => (
          <Paper key={`${v.judge}-${i}`} withBorder radius="sm" p="xs">
            <Group justify="space-between" wrap="nowrap" gap="sm" mb={v.note ? 3 : 0}>
              <Text ff="monospace" size="xs" fw={500} truncate>
                {v.judge}
              </Text>
              <Text size="sm" ff="monospace" fw={700} c={effColor((v.overall ?? 0) / 10)}>
                {v.overall.toFixed(1)}
                <Text span fz={10} c="dimmed">
                  {" "}
                  / 10
                </Text>
              </Text>
            </Group>
            {v.note && (
              <Text fz={11} c="dimmed">
                {v.note}
              </Text>
            )}
          </Paper>
        ))}
      </Stack>
    </div>
  );
}

function SandboxTrial({
  fit,
  notebook,
  activeModel,
  onSelectModel,
}: {
  fit?: SkillFit | null;
  notebook?: SkillNotebook | null;
  activeModel: string | null;
  onSelectModel: (m: string) => void;
}) {
  const { t } = useI18n();
  const cells = notebook?.notebook?.cells ?? [];
  const entries = notebook?.summary?.entries ?? [];
  const hasTrials = !!fit && fit.entries.length > 0;
  return (
    <Card withBorder radius="md" padding="md" mt="md">
      <Group justify="space-between" align="center" mb="xs" wrap="nowrap">
        <Text fw={600}>🧪 {t("trial.title")}</Text>
        {notebook && (
          <Badge color={notebook.stale ? "orange" : "teal"} variant="light">
            {notebook.stale ? t("trial.stale") : t("trial.fresh")}
          </Badge>
        )}
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {t("trial.subtitle")}
      </Text>
      {!hasTrials ? (
        <Alert color="gray" variant="light">
          <Text size="sm">{t("trial.none")}</Text>
          <Text size="xs" c="dimmed" mt={4}>
            {t("trial.noneHint")}
          </Text>
        </Alert>
      ) : (
        <Stack gap="sm">
          <ModelMatrix fit={fit!} activeModel={activeModel} onSelectModel={onSelectModel} />

          {notebook && (
            <Group gap="md">
              <Text size="xs" c="dimmed">
                {t("trial.viewingModel", { model: notebook.model })}
              </Text>
              <Text size="xs" c="dimmed">
                {t("trial.scenario", { name: notebook.scenario })}
              </Text>
              {notebook.created_by && (
                <Text size="xs" c="dimmed">
                  {t("trial.ranBy", { who: notebook.created_by })}
                </Text>
              )}
            </Group>
          )}

          {notebook && <JudgePanel notebook={notebook} />}

          {entries.length > 0 && (
            <div>
              <Text size="sm" fw={600} mb={4}>
                {t("trial.scorecard")}
              </Text>
              <Stack gap="xs">
                {entries.map((e) => (
                  <Paper key={e.label} withBorder radius="sm" p="xs">
                    <Group justify="space-between" mb={4} wrap="nowrap">
                      <Text ff="monospace" size="sm" fw={600}>
                        {e.label}
                      </Text>
                      <Badge color={scoreColor(e)} variant="light">
                        {e.score}
                      </Badge>
                    </Group>
                    <Group gap={4}>
                      {e.passed.map((p) => (
                        <Badge key={p} color="teal" variant="light" size="xs" tt="none" fw={500}>
                          ✓ {p}
                        </Badge>
                      ))}
                      {e.failed.map((f) => (
                        <Badge key={f} color="red" variant="light" size="xs" tt="none" fw={500}>
                          ✗ {f}
                        </Badge>
                      ))}
                    </Group>
                  </Paper>
                ))}
              </Stack>
            </div>
          )}

          {notebook && cells.length > 0 && (
            <div>
              <Text size="sm" fw={600} mb={2}>
                {t("trial.notebookFile")} · {notebook.scenario || "trial"}.ipynb
              </Text>
              <Text size="xs" c="dimmed" mb={6}>
                {t("trial.notebookFileHint")}
              </Text>
              <Group gap="xs">
                <CopyButton value={JSON.stringify(notebook.notebook, null, 1)}>
                  {({ copied, copy }) => (
                    <Button
                      size="compact-xs"
                      variant="light"
                      color={copied ? "teal" : "gray"}
                      onClick={copy}
                    >
                      {copied ? t("common.copied") : t("trial.copyIpynb")}
                    </Button>
                  )}
                </CopyButton>
                <Button
                  size="compact-xs"
                  variant="light"
                  onClick={() =>
                    downloadIpynb(`${notebook.scenario || "trial"}.ipynb`, notebook.notebook)
                  }
                >
                  {t("trial.downloadIpynb")}
                </Button>
              </Group>
            </div>
          )}

          {cells.length > 0 && (
            <Accordion variant="contained">
              <Accordion.Item value="notebook">
                <Accordion.Control>
                  {t("trial.viewNotebook")} · {cells.length}
                </Accordion.Control>
                <Accordion.Panel>
                  <NotebookCells cells={cells} />
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          )}

          <Text size="xs" c="dimmed">
            {t("trial.evidence")}
          </Text>
        </Stack>
      )}
    </Card>
  );
}
