import { AppShell, Group, Text, Title, Anchor } from "@mantine/core";
import { Link, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import SkillDetail from "./pages/SkillDetail";
import Upload from "./pages/Upload";

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
