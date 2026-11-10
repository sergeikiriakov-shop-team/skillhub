import { Anchor } from "@mantine/core";
import { useAuth } from "../auth";

// An inline link to the team's review write-up; renders nothing when the instance has none set.
export default function ReviewDocsLink({ label, size = "sm" }: { label: string; size?: "xs" | "sm" }) {
  const { reviewDocsUrl } = useAuth();
  if (!reviewDocsUrl) return null;
  return (
    <Anchor href={reviewDocsUrl} target="_blank" rel="noreferrer" size={size} title={reviewDocsUrl}>
      {label} ↗
    </Anchor>
  );
}
