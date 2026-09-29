// Each flow styles an authored ordered list. Its literal steps remain in Markdown.
export const diagrams: Record<
  string,
  Record<string, { label: string; layout: "flow" | "pipeline" }>
> = {
  index: {
    pipeline: {
      label: "A7 source to a native program. Zig is a separate toolchain.",
      layout: "flow",
    },
  },
  compiler: {
    pipeline: {
      label: "Compiler stages followed by the separate Zig build.",
      layout: "pipeline",
    },
  },
  "language/arrays-strings": {
    "array-storage": {
      label: "A slice selects part of existing array storage.",
      layout: "flow",
    },
  },
  "language/memory": {
    "reference-access": {
      label: "A nil guard precedes access and allocation cleanup.",
      layout: "flow",
    },
  },
};
