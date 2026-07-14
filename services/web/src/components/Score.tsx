import { Badge, Group, Progress, Stack, Text } from "@mantine/core";

export function scoreColor(value: number | null | undefined): string {
  if (value == null) return "gray";
  if (value >= 8) return "teal";
  if (value >= 6) return "lime";
  if (value >= 4) return "orange";
  return "red";
}

export function ScoreBadge({ value, size = "md" }: { value: number | null; size?: string }) {
  if (value == null) {
    return (
      <Badge color="gray" variant="light" size={size}>
        not scored
      </Badge>
    );
  }
  return (
    <Badge color={scoreColor(value)} variant="filled" size={size}>
      {value.toFixed(1)} / 10
    </Badge>
  );
}

const DIMENSION_LABELS: Record<string, string> = {
  clarity: "Clarity",
  trigger_quality: "Trigger quality",
  completeness: "Completeness",
  reusability: "Reusability",
  safety: "Safety",
  structure: "Structure",
};

export function ScoreBreakdown({ scores }: { scores: Record<string, number> }) {
  const keys = Object.keys(DIMENSION_LABELS).filter((k) => k in scores);
  return (
    <Stack gap="xs">
      {keys.map((key) => (
        <div key={key}>
          <Group justify="space-between" mb={2}>
            <Text size="sm">{DIMENSION_LABELS[key]}</Text>
            <Text size="sm" c="dimmed">
              {scores[key]}/10
            </Text>
          </Group>
          <Progress value={scores[key] * 10} color={scoreColor(scores[key])} size="sm" />
        </div>
      ))}
    </Stack>
  );
}
