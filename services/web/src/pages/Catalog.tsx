import {
  Badge,
  Card,
  Container,
  Group,
  Loader,
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

function SkillCard({ skill, similarity }: { skill: SkillSummary; similarity?: number | null }) {
  return (
    <Card withBorder padding="md" radius="md" component={Link} to={`/skills/${skill.id}`}>
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Text fw={600} truncate>
          {skill.name}
        </Text>
        <ScoreBadge value={skill.overall_score} size="sm" />
      </Group>
      <Text size="xs" c="dimmed" mb="xs">
        by {skill.author ?? "unknown"}
        {similarity != null && ` · ${(similarity * 100).toFixed(0)}% match`}
      </Text>
      <Text size="sm" lineClamp={3} mb="sm">
        {skill.description || "No description."}
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

export default function Catalog() {
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
    { value: "", label: "All categories" },
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
            <Title order={2}>Skill catalog</Title>
            <Text c="dimmed" size="sm">
              {searching ? "Semantic search results" : `${items.length} skill(s)`}
            </Text>
          </div>
        </Group>

        <Group>
          <TextInput
            flex={1}
            placeholder="Search by meaning (e.g. 'run SQL against production safely')"
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
            No skills yet. Import some via the seed command, or add one on the Upload page.
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
