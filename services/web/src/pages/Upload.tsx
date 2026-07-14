import {
  Alert,
  Button,
  Checkbox,
  Container,
  Group,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  ActionIcon,
} from "@mantine/core";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const SAMPLE = `---
name: my-skill
description: >
  ALWAYS use when ... . Do NOT ... .
---

# My Skill

## Workflow
1. ...
`;

interface Ref {
  path: string;
  content: string;
}

export default function Upload() {
  const navigate = useNavigate();
  const [author, setAuthor] = useState("");
  const [content, setContent] = useState("");
  const [format, setFormat] = useState("claude_skill");
  const [evaluate, setEvaluate] = useState(true);
  const [refs, setRefs] = useState<Ref[]>([]);

  const create = useMutation({
    mutationFn: () =>
      api.createSkill({
        content,
        author: author || null,
        source_format: format,
        evaluate,
        references: refs.filter((r) => r.path && r.content),
      }),
    onSuccess: (skill) => navigate(`/skills/${skill.id}`),
  });

  return (
    <Container size="md">
      <Stack gap="md">
        <Title order={2}>Upload a skill</Title>
        <Text c="dimmed" size="sm">
          Paste the raw <code>SKILL.md</code> (with YAML frontmatter). It is parsed, embedded and —
          if the LLM is enabled — evaluated and categorized in the background.
        </Text>

        <TextInput
          label="Author"
          placeholder="your name / team"
          value={author}
          onChange={(e) => setAuthor(e.currentTarget.value)}
        />

        <Select
          label="Source format"
          data={[
            { value: "claude_skill", label: "Claude Code (SKILL.md)" },
            { value: "cursor_mdc", label: "Cursor (.mdc)" },
            { value: "codex_skill", label: "Codex skill" },
            { value: "generic_md", label: "Generic Markdown" },
          ]}
          value={format}
          onChange={(v) => setFormat(v || "claude_skill")}
        />

        <Textarea
          label="SKILL.md content"
          autosize
          minRows={12}
          maxRows={28}
          placeholder={SAMPLE}
          value={content}
          onChange={(e) => setContent(e.currentTarget.value)}
          styles={{ input: { fontFamily: "monospace", fontSize: 13 } }}
        />

        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" mb="xs">
            <Text fw={600}>Reference files (optional)</Text>
            <Button
              size="xs"
              variant="light"
              onClick={() => setRefs([...refs, { path: "references/", content: "" }])}
            >
              Add reference
            </Button>
          </Group>
          <Stack gap="sm">
            {refs.map((ref, i) => (
              <Group key={i} align="flex-start" wrap="nowrap">
                <Stack gap={4} flex={1}>
                  <TextInput
                    size="xs"
                    placeholder="references/tools.md"
                    value={ref.path}
                    onChange={(e) => {
                      const next = [...refs];
                      next[i] = { ...ref, path: e.currentTarget.value };
                      setRefs(next);
                    }}
                  />
                  <Textarea
                    size="xs"
                    autosize
                    minRows={2}
                    placeholder="file content"
                    value={ref.content}
                    onChange={(e) => {
                      const next = [...refs];
                      next[i] = { ...ref, content: e.currentTarget.value };
                      setRefs(next);
                    }}
                  />
                </Stack>
                <ActionIcon
                  color="red"
                  variant="subtle"
                  onClick={() => setRefs(refs.filter((_, j) => j !== i))}
                >
                  ✕
                </ActionIcon>
              </Group>
            ))}
          </Stack>
        </Paper>

        <Checkbox
          label="Evaluate & categorize with Claude after upload"
          checked={evaluate}
          onChange={(e) => setEvaluate(e.currentTarget.checked)}
        />

        {create.isError && (
          <Alert color="red">{(create.error as Error).message}</Alert>
        )}

        <Group justify="flex-end">
          <Button
            onClick={() => create.mutate()}
            loading={create.isPending}
            disabled={!content.trim()}
          >
            Upload skill
          </Button>
        </Group>
      </Stack>
    </Container>
  );
}
