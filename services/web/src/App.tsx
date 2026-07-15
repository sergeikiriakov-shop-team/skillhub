import { AppShell, Group, Text, Title, Anchor } from "@mantine/core";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Categories from "./pages/Categories";
import Methodology from "./pages/Methodology";
import Recommendations from "./pages/Recommendations";
import SkillDetail from "./pages/SkillDetail";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      style={({ isActive }) => ({
        textDecoration: "none",
        fontWeight: isActive ? 700 : 500,
        color: isActive ? "var(--mantine-color-blue-6)" : "var(--mantine-color-dimmed)",
        fontSize: "var(--mantine-font-size-sm)",
      })}
    >
      {label}
    </NavLink>
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
            <Text c="dimmed" size="sm" visibleFrom="sm">
              Claude Code skills registry (read-only dashboard)
            </Text>
          </Group>
          <Group gap="lg">
            <NavItem to="/" label="Catalog" />
            <NavItem to="/categories" label="Categories & ratings" />
            <NavItem to="/recommendations" label="Recommendations" />
            <NavItem to="/methodology" label="Methodology" />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/skills/:id" element={<SkillDetail />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
