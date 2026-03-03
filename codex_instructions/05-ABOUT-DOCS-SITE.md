You are in the existing "link-garden" repository. Create a NEW, COMPLETELY SEPARATE static website project inside this repo, intended to be published independently (e.g., via GitHub Pages or any static host). This static site is NOT the app itself and must not share runtime code with the CLI. It is documentation + philosophy + onboarding only.

Project requirements

1. Create a new directory at repo root: `site/`
2. Treat `site/` as its own mini-repo/project:
   - It should have its own README.md (how to build/serve locally)
   - It should have its own package/tooling choices that are minimal and open-source
3. The site must be STATIC (no server-side rendering required).
4. Prefer minimal tooling:
   - Acceptable options: plain HTML+CSS+JS; or Eleventy (11ty); or Astro; or Vite + vanilla.
   - Choose the simplest that still supports multiple pages and basic navigation.
5. The site must have:
   - A home page
   - An About section (with multiple pages, plus details dropdowns)
   - A Docs section (multiple pages)
   - A clear nav header and footer
   - A basic, calm design (clean typography, light/dark friendly if easy, no heavy frameworks)
6. Write ALL copy/content directly in the site pages (not placeholders).
7. For Docs pages: DO NOT invent features. Read the actual link-garden repo code/README/commands to accurately document what exists right now. If something is unclear, inspect the CLI help, Typer commands, and the docs files in the repo to infer correct usage. Keep docs consistent with implementation.

Information architecture

- / (Home)
- /about/ (index + subpages)
- /about/philosophy/
- /about/privacy/
- /about/architecture/
- /docs/ (index + subpages)
- /docs/quickstart/
- /docs/importing-chrome/
- /docs/organizing-and-frontmatter/
- /docs/exporting/
- /docs/serving/
- /docs/self-hosting/
- /docs/security/
- /docs/troubleshooting/

Content requirements (specific verbiage)
A) Home page content (general audience)
Include the following headline + copy verbatim (you may adjust punctuation slightly but keep the meaning):

Headline:
"Link Garden — bookmarks that grow into a place."

Subhead:
"Link Garden is a local-first bookmark library that stores your links as simple files you can keep, move, and host anywhere — without being trapped inside a browser or a platform."

Then include a short “What it is / What it isn’t” section with bullets, and a CTA button-like link to Docs → Quickstart.

B) About: Philosophy page content (Blob-coded but accessible)
Write a page that includes these paragraphs (you can lightly edit for flow, but preserve the tone and message):

Paragraph 1:
"The internet used to feel like a neighborhood. Now it often feels like a mall. Link Garden is an attempt to build something small and human again: a place where links can live without being sorted by an algorithm or trapped behind a login."

Paragraph 2:
"A Link Garden is not a feed. It’s not a timeline. It doesn’t demand constant attention. It’s closer to a personal library, or a porch with a few good signposts — something you return to when you want to remember what mattered."

Paragraph 3:
"Most tools for saving information are built around capture. Link Garden is built around keeping. Files you can own. Folders you can understand. Exports you can host. A garden you can tend."

End with a short section titled "The point" and include these bullets verbatim:

- "Local-first by default."
- "Simple files, not a proprietary database."
- "Sharing is opt-in, not assumed."
- "A future-friendly web: small sites, not mega-platforms."

C) About: Architecture page with expandable details sections
Create an About page that provides an overview for non-technical readers, then includes multiple <details> dropdowns (native HTML) explaining each component of the stack.

Required <details> sections (one each):

- "Files on disk (Markdown + frontmatter)"
- "Indexing (why an index exists)"
- "Importing (Chrome bookmarks)"
- "Exporting (HTML / Markdown / JSON)"
- "Serving locally"
- "Self-hosting with nginx (optional)"
- "Security & visibility (private/unlisted/public)"

Each <details> section should include:

- A plain-language explanation
- A short “Why this exists” sentence
- A small code block showing an example (for frontmatter, CLI command, or nginx snippet as appropriate)

D) About: Privacy page
Write a privacy stance page (not a legal policy) that explains:

- The project’s intent to avoid Big Tech lock-in
- That users can choose what to publish
- That the safest default is local-only
- Encourage people not to publish private bookmarks publicly
  Include a “Practical privacy tips” list (6–10 bullets).

E) Docs pages (must match repo reality)
Docs pages must be accurate to what is in the link-garden codebase. Use:

- `link-garden --help` and subcommand help output
- Existing README content
- Any docs already in the repo
- Tests if helpful
  Document:
- Installation
- Creating a garden directory
- Importing Chrome JSON, folder preservation, and dedupe modes
- Listing/searching
- Export formats and what they include
- The meaning of visibility scopes if implemented; otherwise, document current behavior and add a TODO box for planned visibility model
- “Doctor” command and common issues
- “Serving” (if serve exists; otherwise add a page that says it’s planned and recommends safe alternatives)
- Self-hosting guidance and nginx reverse proxy setup (keep it clearly optional and warn about security)

Important: If some security features mentioned (like serve, visibility scopes, nginx docs) do NOT exist yet in the main repo, still create the docs pages, but:

- Clearly label planned items as "Planned" and keep them non-deceptive.
- Prefer linking to SECURITY.md and docs in the main repo when relevant.

Design requirements

- Clean layout, readable typography, responsive.
- No external CDNs required to render (fonts should be system fonts).
- A small set of reusable styles (e.g., a single CSS file).
- Add a simple navigation with active link styling.
- Add a footer with:
  - "Link Garden is open source."
  - Links: GitHub repo (relative link ok), SECURITY, Docs.

Build/serve requirements

- Provide a single command to run locally (e.g., `npm run dev` or `python -m http.server`).
- If using a tool like 11ty/Astro/Vite, include package.json and instructions in site/README.md.
- Add a minimal CI check in the main repo (optional) that ensures `site/` builds.

Integration with main repo

- Add to the main repo README.md a section:
  - "Website"
  - Explain that `site/` is a standalone static site project
  - Provide commands to run it locally
  - Mention GitHub Pages deployment possibility (no need to configure fully unless simple)

Deliver output

- Implement the site structure with actual files.
- Ensure links between pages work.
- Include all copy requested above.
- Ensure docs reflect the current repo state (don’t invent commands/features).
- Provide a short summary of what you built and how to run it.

Proceed now.
