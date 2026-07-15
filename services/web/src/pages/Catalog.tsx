import {
  Badge,
  Card,
  Container,
  Group,
  Loader,
  Paper,
  Select,
  SimpleGrid,
  Text,
  TextInput,
  Title,
  Stack,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, SkillSummary } from "../api";
import { ScoreBadge } from "../components/Score";
import { useI18n } from "../i18n";
import type { TFunc } from "../i18n";

function SkillCard({ skill, similarity }: { skill: SkillSummary; similarity?: number | null }) {
  const { t } = useI18n();
  return (
    <Card withBorder padding="md" radius="md" component={Link} to={`/skills/${skill.id}`}>
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Text fw={600} truncate>
          {skill.name}
        </Text>
        <ScoreBadge value={skill.overall_score} size="sm" />
      </Group>
      <Text size="xs" c="dimmed" mb="xs">
        {t("catalog.by", { author: skill.author ?? t("catalog.unknownAuthor") })}
        {similarity != null && ` · ${t("catalog.match", { pct: (similarity * 100).toFixed(0) })}`}
      </Text>
      <Text size="sm" lineClamp={3} mb="sm">
        {skill.description || t("catalog.noDescription")}
      </Text>
      <Group gap={4}>
        {skill.categories.slice(0, 3).map((c) => (
          <Badge key={c.key} variant="light" size="sm">
            {c.label}
          </Badge>
        ))}
      </Group>
    </Card>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <Paper withBorder radius="md" p="sm" miw={110}>
      <Text size="xl" fw={700}>
        {value}
      </Text>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
    </Paper>
  );
}

function StatsBar({ t }: { t: TFunc }) {
  const { data } = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  if (!data) return null;
  const pct = data.total ? Math.round((data.evaluated / data.total) * 100) : 0;
  return (
    <Group gap="sm" align="center">
      <StatTile label={t("stats.skills")} value={String(data.total)} />
      <StatTile label={t("stats.evaluated")} value={`${data.evaluated} (${pct}%)`} />
      <StatTile
        label={t("stats.avgScore")}
        value={data.avg_overall != null ? data.avg_overall.toFixed(1) : "—"}
      />
      <Group gap={4}>
        {data.by_category.slice(0, 5).map((c) => (
          <Badge key={c.key} variant="light" size="lg">
            {c.label}: {c.count}
          </Badge>
        ))}
      </Group>
    </Group>
  );
}

export default function Catalog() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [debounced] = useDebouncedValue(search, 300);
  const [category, setCategory] = useState<string | null>(null);

  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });

  const searching = debounced.trim().length > 0;
  const listQuery = useQuery({
    queryKey: ["skills", category],
    queryFn: () => api.listSkills(undefined, category ?? undefined),
    enabled: !searching,
  });
  const searchQuery = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => api.search(debounced),
    enabled: searching,
  });

  const isLoading = searching ? searchQuery.isLoading : listQuery.isLoading;
  const items: { skill: SkillSummary; similarity?: number | null }[] = searching
    ? (searchQuery.data ?? []).map((h) => ({ skill: h.skill, similarity: h.similarity }))
    : (listQuery.data ?? []).map((s) => ({ skill: s }));

  const categoryOptions = [
    { value: "", label: t("catalog.allCategories") },
    ...(categoriesQuery.data ?? []).map((c) => ({
      value: c.key,
      label: `${c.label} (${c.skill_count})`,
    })),
  ];

  return (
    <Container size="xl">
      <Stack gap="md">
        <Group justify="space-between" align="flex-end">
          <div>
            <Title order={2}>{t("catalog.title")}</Title>
            <Text c="dimmed" size="sm">
              {searching ? t("catalog.searchResults") : t("catalog.count", { count: items.length })}
            </Text>
          </div>
        </Group>

        <StatsBar t={t} />

        <Group>
          <TextInput
            flex={1}
            placeholder={t("catalog.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />
          <Select
            w={220}
            data={categoryOptions}
            value={category ?? ""}
            onChange={(v) => setCategory(v || null)}
            disabled={searching}
            allowDeselect={false}
          />
        </Group>

        {isLoading ? (
          <Group justify="center" mt="xl">
            <Loader />
          </Group>
        ) : items.length === 0 ? (
          <Text c="dimmed" ta="center" mt="xl">
            {t("catalog.empty")}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {items.map(({ skill, similarity }) => (
              <SkillCard key={skill.id} skill={skill} similarity={similarity} />
            ))}
          </SimpleGrid>
        )}
      </Stack>
    </Container>
  );
}
