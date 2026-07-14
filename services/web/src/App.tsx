import { AppShell, Group, Text, Title, Anchor } from "@mantine/core";
import { Link, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import SkillDetail from "./pages/SkillDetail";

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
              Claude Code skills registry (read-only dashboard)
            </Text>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/skills/:id" element={<SkillDetail />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
