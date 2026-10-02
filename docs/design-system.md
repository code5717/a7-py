# A7 Docs Design System

Moved from `.interface-design/system.md` on 2026-10-02 so all shared docs live under `docs/`. Local agent config stays ignored; this file is the tracked design record.


## Intent

- Human: compiler contributor, language learner, and test maintainer.
- Goal: find exact commands and rules fast.
- Feel: large, clear, direct, and technical with strong hierarchy.

## Domain

- Compiler stages
- Token streams
- Syntax trees
- Semantic checks
- Code generation
- Example driven learning

## Color World

- Oxide teal for active technical signals
- Warm paper base for long reading
- Brass accent for warnings and status
- Moss green for pass and healthy states
- Iron ink for dense text blocks

## Signature

The signature element is a large atlas panel style.

Each page opens with a high contrast title block.

Navigation cards use short summaries and dense route grouping.

Visual references keep large panels and direct labels.

## Defaults Replaced

- Replaced template sidebars with custom summary links.
- Replaced small body type with a large reading scale.
- Replaced generic card grid feel with atlas themed surfaces.

## Token Rules

- Use only CSS custom properties from `site/src/styles/tokens.css`.
- Keep one accent family for interaction state.
- Keep one signal family for status state.
- Keep one depth strategy based on surface lightness shift and soft borders.

## Typography

- Display: Fraunces
- Body: Manrope
- Mono: JetBrains Mono

## Spacing

Base unit is 8px.

Use fixed scale from `--space-1` to `--space-7`.

## Components

- Sticky top header with quick links
- Sticky section nav on desktop
- Card grid for route and visual jumps
- KPI cards for current project metrics
- Large preformatted blocks for commands and code

## Validation Checks

- Squint test keeps clear hierarchy.
- Swap test still shows A7 identity after font swap check.
- Mobile view keeps readable block width.
