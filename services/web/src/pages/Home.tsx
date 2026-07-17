import { Badge, Card, Container, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useI18n } from "../i18n";

function ServiceCard({
  to,
  title,
  desc,
  stat,
}: {
  to: string;
  title: string;
  desc: string;
  stat: string | null;
}) {
  const { t } = useI18n();
  return (
    <Card withBorder radius="md" padding="xl" component={Link} to={to} style={{ height: "100%" }}>
      <Stack gap="sm" h="100%">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Title order={3}>{title}</Title>
          {stat && (
            <Badge variant="light" size="lg">
              {stat}
            </Badge>
          )}
        </Group>
        <Text c="dimmed" size="sm" style={{ flex: 1 }}>
          {desc}
        </Text>
        <Text c="blue" fw={600} size="sm">
          {t("home.enter")} →
        </Text>
      </Stack>
    </Card>
  );
}

export default function Home() {
  const { t } = useI18n();
  const statsQuery = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const reviewsQuery = useQuery({ queryKey: ["reviews", "all"], queryFn: () => api.listReviews() });

  const stats = statsQuery.data;
  const skillsStat = stats
    ? t("home.skills.stat", {
        total: stats.total,
        avg: stats.avg_overall != null ? stats.avg_overall.toFixed(1) : "—",
      })
    : null;

  const openCount = (reviewsQuery.data ?? []).filter(
    (r) => r.status === "submitted" || r.status === "changes_requested",
  ).length;
  const reviewsStat = reviewsQuery.data ? t("home.reviews.stat", { open: openCount }) : null;

  return (
    <Container size="lg" mt="lg">
      <Stack gap="xl">
        <div>
          <Title order={1}>{t("home.title")}</Title>
          <Text c="dimmed">{t("home.subtitle")}</Text>
        </div>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
          <ServiceCard
            to="/skills"
            title={t("home.skills.title")}
            desc={t("home.skills.desc")}
            stat={skillsStat}
          />
          <ServiceCard
            to="/reviews"
            title={t("home.reviews.title")}
            desc={t("home.reviews.desc")}
            stat={reviewsStat}
          />
        </SimpleGrid>
      </Stack>
    </Container>
  );
}
