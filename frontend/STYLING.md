# Styling architecture

PolicyOS uses design tokens, CSS Modules, and shared React primitives. Tailwind remains available to
third-party styles but is not the default authoring pattern for product UI.

## Where styles belong

- `app/globals.css`: framework imports, design tokens, reset rules, base typography, and global
  accessibility behavior only.
- `components/ui/<component>`: one folder per reusable control, with its implementation, barrel
  export, and colocated CSS Module when it has styles. Use these before introducing another button,
  badge, field, panel, or table implementation.
- `components/features/<feature>/<component>`: one folder per feature-owned component, including its
  colocated CSS Module when needed. A feature-level barrel is the public import boundary for routes.
- `components/shared`: application-specific components used by multiple features. Keep this smaller
  than the feature layer and move a component here only after it has multiple consumers.
- `components/shell`: application chrome and integration components, including the scoped legacy
  surface styles owned by the shell.
- `*.module.css` beside a component or route: component- and feature-specific layout and states.
- The scoped surface modules imported by `components/shell/app-shell/app-shell.tsx`: existing semantic page
  classes, grouped by ownership. They are constrained by the shell's generated scope class so they
  cannot leak into the landing page or Learn documentation.

## Tokens

Use the color, surface, spacing, radius, typography, and shadow variables in `app/globals.css`.
Add a token when a value represents a repeated design decision; keep one-off feature geometry in the
feature's module.

## Shared primitives

Import from `@/components/ui`:

- `Button` and `ButtonLink`: `primary`, `secondary`, and `danger` variants; default and small sizes.
- `Badge`: neutral, accent, success, warning, and danger tones.
- `FormField`, `TextInput`, and `SelectInput`: labels, hints, validation, and controls.
- `Panel`, `PanelHeader`, and `PanelBody`: bordered product surfaces.
- `DataTable`: shared table styling. Use a clipped `Panel` around tables that need a framed surface,
  and a plain feature-owned overflow container when horizontal scrolling is needed.

Keep data-driven values such as progress widths or documentation nesting depth as inline custom
values when CSS cannot know them. Static visual adjustments belong in a CSS Module.
