import { Badge, Group, Progress, Stack, Text } from "@mantine/core";
import { useI18n } from "../i18n";

export function scoreColor(value: number | null | undefined): string {
  if (value == null) return "gray";
  if (value >= 8) return "teal";
  if (value >= 6) return "lime";
  if (value >= 4) return "orange";
  return "red";
}

export function ScoreBadge({ value, size = "md" }: { value: number | null; size?: string }) {
  const { t } = useI18n();
  if (value == null) {
    return (
      <Badge color="gray" variant="light" size={size}>
        {t("score.notScored")}
      </Badge>
    );
  }
  return (
    <Badge color={scoreColor(value)} variant="filled" size={size}>
      {value.toFixed(1)} / 10
    </Badge>
  );
}

// Fixed dimension order; the label for each comes from the i18n dictionary (`dim.<key>`).
const DIMENSION_KEYS = [
  "clarity",
  "trigger_quality",
  "completeness",
  "reusability",
  "safety",
  "structure",
];

export function ScoreBreakdown({ scores }: { scores: Record<string, number> }) {
  const { t } = useI18n();
  const keys = DIMENSION_KEYS.filter((k) => k in scores);
  return (
    <Stack gap="xs">
      {keys.map((key) => (
        <div key={key}>
          <Group justify="space-between" mb={2}>
            <Text size="sm">{t(`dim.${key}`)}</Text>
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
