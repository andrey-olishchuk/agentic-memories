# Memories

Each subfolder is one memory type. A folder becomes discoverable when it contains a `MEMORY.md` manifest at its root.

The shipped default set intentionally contains only `default`, a universal fallback for arbitrary text or stringified JSON:

```text
memories/
  default/
    MEMORY.md
```

There is no `bindings.yaml` or registration file. Applications route by the manifest `name`.
