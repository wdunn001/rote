---
slug: astro-section-rename-redirects
name: Astro section-rename redirects generated from the content dir
language: javascript
intent: When a content section moves to a new URL prefix, keep every old URL alive by generating /OLD/<slug> -> /NEW/<slug> redirects at astro.config load time, read from the content directory so future entries are covered automatically.
tags: astro, redirects, static-site, url-migration
---

# When to use

You renamed an Astro content section's route (e.g. `/news/` -> `/analysis/`) and existing URLs are already public/shared. Static-mode Astro emits one redirect stub per entry, so the old paths keep resolving. Reading the dir means new entries get the redirect for free without editing config.

# Placeholders

| Token | Meaning | Example |
|---|---|---|
| `${CONTENT_DIR}` | path to the section's content folder | `./src/content/analysis` |
| `${OLD}` | old route prefix (no slashes) | `news` |
| `${NEW}` | new route prefix (no slashes) | `analysis` |
| `${OVERRIDES}` | explicit one-off redirects that must win over the generated pattern (more-specific static routes take priority) | `"/news/x": "/articles/x"` |

# Snippet

```js
import { readdirSync } from "node:fs";
import { defineConfig } from "astro/config";

const slugs = readdirSync(new URL("${CONTENT_DIR}", import.meta.url))
  .filter((f) => /\.(md|mdx)$/.test(f))
  .map((f) => f.replace(/\.(md|mdx)$/, ""));

const redirects = {
  "/${OLD}": "/${NEW}",
  "/${OLD}/rss.xml": "/${NEW}/rss.xml",
  ${OVERRIDES}
  ...Object.fromEntries(slugs.map((s) => [`/${OLD}/${s}`, `/${NEW}/${s}`])),
};

export default defineConfig({
  redirects,
  // ...rest of config
});
```

# Notes

- Static (SSG) Astro generates a redirect HTML stub per *static* source path; this enumerates them from disk rather than relying on a dynamic `[...slug]` pattern (which SSG does not auto-enumerate).
- Order matters only by specificity, not object order: an explicit `${OVERRIDES}` entry (a static path) wins over the spread. Verify with a build + a `curl` of one old URL.
- Pairs with the anti-pattern `blanket-route-segment-replace-corrupts-imports`: change the config redirect SOURCES by hand, never via a tree-wide replace of the old segment.
