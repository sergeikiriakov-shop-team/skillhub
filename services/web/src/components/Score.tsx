import { Badge, Group, Progress, Stack, Text, Tooltip } from "@mantine/core";
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

// The empirical headline: best (skill, model) effectiveness (0..1) across the sandbox-trial
// matrix — judge-panel graded, gated by the objective scorecard. Same color bands as ScoreBadge
// (0..1 <-> 0..10) so the two read consistently wherever both appear.
export function EffectivenessBadge({
  value,
  model,
  size = "md",
}: {
  value: number | null;
  model?: string | null;
  size?: string;
}) {
  const { t } = useI18n();
  if (value == null) {
    return (
      <Badge color="gray" variant="light" size={size}>
        {t("score.notTrialed")}
      </Badge>
    );
  }
  const badge = (
    <Badge color={scoreColor(value * 10)} variant="filled" size={size}>
      {Math.round(value * 100)}%
    </Badge>
  );
  return model ? (
    <Tooltip label={t("score.effectivenessTitle", { model })} withArrow>
      {badge}
    </Tooltip>
  ) : (
    badge
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

export function ScoreBreakdown({
  scores,
  dimensionKeys = DIMENSION_KEYS,
}: {
  scores: Record<string, number>;
  dimensionKeys?: string[];
}) {
  const { t } = useI18n();
  const keys = dimensionKeys.filter((k) => k in scores);
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
