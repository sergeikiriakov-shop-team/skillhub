import { Container, Group, Loader } from "@mantine/core";

/** Centered full-page loading state, shared by the top-level pages. */
export default function PageLoader({ size = "md" }: { size?: string }) {
  return (
    <Container size={size}>
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    </Container>
  );
}
