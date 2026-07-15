import {
  Anchor,
  Badge,
  Card,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, SkillSummary } from "../api";
import { ScoreBadge } from "../components/Score";

function byScoreDesc(a: SkillSummary, b: SkillSummary): number {
  return (b.overall_score ?? -1) - (a.overall_score ?? -1);
}

function prettyGroup(key: string): string {
  return key === "(ungrouped)" ? "ungrouped" : key.replace(/-/g, " ");
}

function RankTable({ skills, bestId }: { skills: SkillSummary[]; bestId?: number }) {
  return (
    <Table verticalSpacing="xs" horizontalSpacing="sm" highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={36}>#</Table.Th>
          <Table.Th>Skill</Table.Th>
          <Table.Th>Author</Table.Th>
          <Table.Th ta="right">Score</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {skills.map((s, i) => {
          const isBest = s.id === bestId;
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
                      ✦ synthesized
                    </Badge>
                  )}
                  {isBest && (
                    <Badge size="xs" color="yellow" variant="filled">
                      ★ best
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
                <ScoreBadge value={s.overall_score} size="sm" />
              </Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

export default function Categories() {
  const skillsQuery = useQuery({ queryKey: ["skills", null], queryFn: () => api.listSkills() });
  const catsQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });

  if (skillsQuery.isLoading || catsQuery.isLoading) {
    return (
      <Container size="lg">
        <Group justify="center" mt="xl">
          <Loader />
        </Group>
      </Container>
    );
  }

  const skills = skillsQuery.data ?? [];
  const cats = catsQuery.data ?? [];

  // Global narrow-group ranking: which skill is the best within each task_group (only meaningful
  // when the group has more than one skill — that is the real "same job" competition).
  const byTaskGroup = new Map<string, SkillSummary[]>();
  for (const s of skills) {
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

  // Broad grouping: skills per category (a skill can appear in several).
  const byCategory = new Map<string, SkillSummary[]>();
  for (const s of skills) {
    for (const c of s.categories) {
      const list = byCategory.get(c.key) ?? [];
      list.push(s);
      byCategory.set(c.key, list);
    }
  }

  const leaderboard = [...skills].filter((s) => s.overall_score != null).sort(byScoreDesc).slice(0, 5);

  // Service-generated "ideal" skills, each merged from the other members of its task group.
  const synthesized = skills
    .filter((s) => s.source_type === "synthesized")
    .sort(byScoreDesc);

  return (
    <Container size="lg">
      <Stack gap="lg">
        <div>
          <Title order={2}>Categories &amp; ratings</Title>
          <Text c="dimmed" size="sm">
            The output of the registry. Skills are grouped on two levels — a broad category, then
            the narrow <b>task group</b> (their specific job). Within a task group with more than one
            skill (a real "same job" competition) the ★ marks the top-rated one.
          </Text>
        </div>

        {synthesized.length > 0 && (
          <Card withBorder radius="md" padding="md" bg="var(--mantine-color-grape-light)">
            <Group gap="xs" mb={4} align="center">
              <Title order={4}>✦ Synthesized ideals</Title>
              <Badge color="grape" variant="light">
                {synthesized.length}
              </Badge>
            </Group>
            <Text size="sm" c="dimmed" mb="md">
              Skills the registry generated itself — each merges the best of one task group via the
              stored synthesis algorithm. The nested list shows the source skills it was built from.
            </Text>
            <Stack gap="sm">
              {synthesized.map((ideal) => {
                const sources = (byTaskGroup.get(ideal.task_group ?? "") ?? []).filter(
                  (s) => s.id !== ideal.id,
                );
                return (
                  <Paper withBorder radius="md" p="sm" key={ideal.id}>
                    <Group justify="space-between" wrap="nowrap">
                      <Group gap={8} wrap="nowrap">
                        <Anchor component={Link} to={`/skills/${ideal.id}`} fw={700}>
                          {ideal.name}
                        </Anchor>
                        <Badge size="xs" color="grape" variant="filled">
                          ✦ synthesized
                        </Badge>
                        {ideal.task_group && (
                          <Badge
                            size="xs"
                            variant="outline"
                            styles={{ label: { textTransform: "none" } }}
                          >
                            {prettyGroup(ideal.task_group)}
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
                          merged from
                        </Text>
                        <Stack gap={4}>
                          {sources.map((s) => (
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
            Overall leaderboard
          </Title>
          {leaderboard.length === 0 ? (
            <Text size="sm" c="dimmed">
              No scored skills yet.
            </Text>
          ) : (
            <RankTable skills={leaderboard} bestId={leaderboard[0]?.id} />
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
                  <Badge variant="light">{list.length} skill(s)</Badge>
                  {avg != null && (
                    <Badge variant="light" color="teal">
                      avg {avg.toFixed(1)}
                    </Badge>
                  )}
                </Group>
              </Group>
              <Text size="sm" c="dimmed" mb="sm">
                {cat.description}
              </Text>

              {list.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No skills in this category yet.
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
                          {prettyGroup(tg)}
                        </Badge>
                        {arr.length > 1 && (
                          <Text size="xs" c="dimmed">
                            {arr.length} competing
                          </Text>
                        )}
                      </Group>
                      <RankTable skills={arr} bestId={bestInGroup.get(tg)} />
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
