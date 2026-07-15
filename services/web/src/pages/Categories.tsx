import { Anchor, Badge, Card, Container, Group, Paper, Stack, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, SkillSummary } from "../api";
import PageLoader from "../components/PageLoader";
import { ScoreBadge } from "../components/Score";
import { useI18n } from "../i18n";
import type { TFunc } from "../i18n";

function byScoreDesc(a: SkillSummary, b: SkillSummary): number {
  return (b.overall_score ?? -1) - (a.overall_score ?? -1);
}

// The slug itself is data; only the "(ungrouped)" bucket gets a translated label.
function prettyGroup(key: string, t: TFunc): string {
  return key === "(ungrouped)" ? t("group.ungrouped") : key.replace(/-/g, " ");
}

function RankTable({
  skills,
  bestId,
  currentVersion,
}: {
  skills: SkillSummary[];
  bestId?: number;
  currentVersion?: string;
}) {
  const { t } = useI18n();
  return (
    <Table verticalSpacing="xs" horizontalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={36}>{t("table.rank")}</Table.Th>
          <Table.Th>{t("table.skill")}</Table.Th>
          <Table.Th>{t("table.author")}</Table.Th>
          <Table.Th ta="right">{t("table.score")}</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {skills.map((s, i) => {
          const isBest = s.id === bestId;
          const stale =
            currentVersion != null && s.rubric_version != null && s.rubric_version !== currentVersion;
          return (
            <Table.Tr key={s.id}>
              <Table.Td c="dimmed">{i + 1}</Table.Td>
              <Table.Td>
                <Group gap={6} wrap="nowrap">
                  <Anchor component={Link} to={`/skills/${s.id}`} fw={isBest ? 700 : 500}>
                    {s.name}
                  </Anchor>
                  {s.source_type === "synthesized" && (
                    <Badge size="xs" color="grape" variant="filled">
                      {t("badge.synthesized")}
                    </Badge>
                  )}
                  {isBest && (
                    <Badge size="xs" color="yellow" variant="filled">
                      {t("badge.best")}
                    </Badge>
                  )}
                </Group>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {s.author ?? "—"}
                </Text>
              </Table.Td>
              <Table.Td ta="right">
                <Group gap={6} justify="flex-end" wrap="nowrap">
                  {stale && (
                    <Badge size="xs" color="gray" variant="outline" title={t("badge.staleTitle")}>
                      {t("badge.stale", { v: s.rubric_version ?? "" })}
                    </Badge>
                  )}
                  <ScoreBadge value={s.overall_score} size="sm" />
                </Group>
              </Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

export default function Categories() {
  const { t } = useI18n();
  const skillsQuery = useQuery({ queryKey: ["skills", null], queryFn: () => api.listSkills() });
  const catsQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: api.health });

  if (skillsQuery.isLoading || catsQuery.isLoading) {
    return <PageLoader size="lg" />;
  }

  const skills = skillsQuery.data ?? [];
  const cats = catsQuery.data ?? [];
  const currentVersion = healthQuery.data?.rubric_version;

  // Synthesized "ideals" are the registry's own output and get their own section below; they are
  // excluded from the competitive rankings, the leaderboard and the category averages so they
  // don't steal the ★ best badge from a human skill or inflate aggregates.
  const humanSkills = skills.filter((s) => s.source_type !== "synthesized");
  const synthesized = skills.filter((s) => s.source_type === "synthesized").sort(byScoreDesc);

  // Narrow-group ranking over human skills: the best within each task_group (only meaningful when
  // the group has more than one skill — the real "same job" competition).
  const byTaskGroup = new Map<string, SkillSummary[]>();
  for (const s of humanSkills) {
    if (!s.task_group) continue;
    const list = byTaskGroup.get(s.task_group) ?? [];
    list.push(s);
    byTaskGroup.set(s.task_group, list);
  }
  const bestInGroup = new Map<string, number>();
  for (const [tg, list] of byTaskGroup) {
    list.sort(byScoreDesc);
    if (list.length > 1 && list[0].overall_score != null) bestInGroup.set(tg, list[0].id);
  }

  // Broad grouping over human skills (a skill can appear in several categories).
  const byCategory = new Map<string, SkillSummary[]>();
  for (const s of humanSkills) {
    for (const c of s.categories) {
      const list = byCategory.get(c.key) ?? [];
      list.push(s);
      byCategory.set(c.key, list);
    }
  }

  const leaderboard = humanSkills.filter((s) => s.overall_score != null).sort(byScoreDesc).slice(0, 5);

  return (
    <Container size="lg">
      <Stack gap="lg">
        <div>
          <Title order={2}>{t("categories.title")}</Title>
          <Text c="dimmed" size="sm">
            {t("categories.intro")}
          </Text>
        </div>

        {synthesized.length > 0 && (
          <Card withBorder radius="md" padding="md" bg="var(--mantine-color-grape-light)">
            <Group gap="xs" mb={4} align="center">
              <Title order={4}>{t("categories.synthTitle")}</Title>
              <Badge color="grape" variant="light">
                {synthesized.length}
              </Badge>
            </Group>
            <Text size="sm" c="dimmed" mb="md">
              {t("categories.synthIntro")}
            </Text>
            <Stack gap="sm">
              {synthesized.map((ideal) => {
                const sources = byTaskGroup.get(ideal.task_group ?? "") ?? [];
                return (
                  <Paper withBorder radius="md" p="sm" key={ideal.id}>
                    <Group justify="space-between" wrap="nowrap">
                      <Group gap={8} wrap="nowrap">
                        <Anchor component={Link} to={`/skills/${ideal.id}`} fw={700}>
                          {ideal.name}
                        </Anchor>
                        <Badge size="xs" color="grape" variant="filled">
                          {t("badge.synthesized")}
                        </Badge>
                        {ideal.task_group && (
                          <Badge
                            size="xs"
                            variant="outline"
                            styles={{ label: { textTransform: "none" } }}
                          >
                            {prettyGroup(ideal.task_group, t)}
                          </Badge>
                        )}
                      </Group>
                      <ScoreBadge value={ideal.overall_score} size="sm" />
                    </Group>
                    {sources.length > 0 && (
                      <div
                        style={{
                          marginTop: 10,
                          paddingLeft: 12,
                          borderLeft: "2px solid var(--mantine-color-grape-outline)",
                        }}
                      >
                        <Text size="xs" c="dimmed" mb={4}>
                          {t("categories.mergedFrom")}
                        </Text>
                        <Stack gap={4}>
                          {[...sources].sort(byScoreDesc).map((s) => (
                            <Group key={s.id} justify="space-between" wrap="nowrap">
                              <Text size="sm">
                                <Anchor component={Link} to={`/skills/${s.id}`}>
                                  {s.name}
                                </Anchor>
                                <Text span c="dimmed" size="xs">
                                  {" "}
                                  · {s.author ?? "—"}
                                </Text>
                              </Text>
                              <ScoreBadge value={s.overall_score} size="xs" />
                            </Group>
                          ))}
                        </Stack>
                      </div>
                    )}
                  </Paper>
                );
              })}
            </Stack>
          </Card>
        )}

        <Card withBorder radius="md" padding="md">
          <Title order={4} mb="sm">
            {t("categories.leaderboard")}
          </Title>
          {leaderboard.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("categories.noScored")}
            </Text>
          ) : (
            <RankTable skills={leaderboard} bestId={leaderboard[0]?.id} currentVersion={currentVersion} />
          )}
        </Card>

        {cats.map((cat) => {
          const list = byCategory.get(cat.key) ?? [];
          const scored = list.filter((s) => s.overall_score != null);
          const avg = scored.length
            ? scored.reduce((n, s) => n + (s.overall_score ?? 0), 0) / scored.length
            : null;

          // Sub-group this category's skills by their narrow task_group.
          const groups = new Map<string, SkillSummary[]>();
          for (const s of list) {
            const key = s.task_group ?? "(ungrouped)";
            const arr = groups.get(key) ?? [];
            arr.push(s);
            groups.set(key, arr);
          }
          const orderedGroups = [...groups.entries()]
            .map(([tg, arr]) => [tg, [...arr].sort(byScoreDesc)] as const)
            .sort((a, b) => byScoreDesc(a[1][0], b[1][0]));

          return (
            <Card withBorder radius="md" padding="md" key={cat.key}>
              <Group justify="space-between" align="center" mb={4} wrap="nowrap">
                <Title order={4}>{cat.label}</Title>
                <Group gap="xs">
                  <Badge variant="light">{t("categories.count", { count: list.length })}</Badge>
                  {avg != null && (
                    <Badge variant="light" color="teal">
                      {t("categories.avg", { v: avg.toFixed(1) })}
                    </Badge>
                  )}
                </Group>
              </Group>
              <Text size="sm" c="dimmed" mb="sm">
                {cat.description}
              </Text>

              {list.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("categories.noneInCategory")}
                </Text>
              ) : (
                <Stack gap="md">
                  {orderedGroups.map(([tg, arr]) => (
                    <div key={tg}>
                      <Group gap="xs" mb={4} align="center">
                        <Badge
                          variant="outline"
                          size="sm"
                          styles={{ label: { textTransform: "none" } }}
                        >
                          {prettyGroup(tg, t)}
                        </Badge>
                        {arr.length > 1 && (
                          <Text size="xs" c="dimmed">
                            {t("categories.competing", { count: arr.length })}
                          </Text>
                        )}
                      </Group>
                      <RankTable skills={arr} bestId={bestInGroup.get(tg)} currentVersion={currentVersion} />
                    </div>
                  ))}
                </Stack>
              )}
            </Card>
          );
        })}
      </Stack>
    </Container>
  );
}
