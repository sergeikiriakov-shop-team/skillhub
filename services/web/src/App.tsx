import { AppShell, Badge, Group, Text, Title, Anchor } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { Link, Route, Routes } from "react-router-dom";
import { api } from "./api";
import Catalog from "./pages/Catalog";
import SkillDetail from "./pages/SkillDetail";
import Upload from "./pages/Upload";

function HealthBadge() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: api.health });
  if (!data) return null;
  return (
    <Badge color={data.llm_enabled ? "teal" : "gray"} variant="light">
      LLM {data.llm_enabled ? `on · ${data.model}` : "off"}
    </Badge>
  );
}

export default function App() {
  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Anchor component={Link} to="/" underline="never">
              <Title order={3}>🧩 SkillHub</Title>
            </Anchor>
            <Text c="dimmed" size="sm">
              Claude Code skills registry
            </Text>
          </Group>
          <Group>
            <Anchor component={Link} to="/">
              Catalog
            </Anchor>
            <Anchor component={Link} to="/upload">
              Upload
            </Anchor>
            <HealthBadge />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/skills/:id" element={<SkillDetail />} />
          <Route path="/upload" element={<Upload />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
