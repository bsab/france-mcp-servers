# Contributing to France MCP Servers

## Adding an MCP server

1. **Fork this repository** to contribute.
2. Create a `kebab-case.json` file in `servers/`.
3. Complete the fields in [`schema/server.schema.json`](schema/server.schema.json).
4. Validate and regenerate the README, then include it in your commit:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements.txt
.venv/bin/python scripts/validate_servers.py
.venv/bin/python scripts/build_readme.py
```

5. Open a pull request with a title such as `feat: add Example MCP Server`.

> README catalog tables and badges are generated from `servers/`. Do not edit them
> manually: regeneration will overwrite those changes. Write descriptions, notes,
> documentation and issue reports in English. Official project names may retain French wording.

### Listing requirements

- The project must implement the **Model Context Protocol**; an API alone is not enough.
- It must be relevant to French data, laws or services.
- It must provide a public repository, documentation site or MCP endpoint.
- It must have sufficient usage documentation.
- Verify repository ownership, documented transport and setup requirements against
  canonical sources. Never invent endpoints, credentials, capabilities or star counts.
- Use `site_url` for the documentation consulted, preferably pinned to a commit.
  Record the metadata verification date in optional `last_verified` (`YYYY-MM-DD`).
  This is not a health check or a Ready score assessment.
- Record GitHub stars as a snapshot. Use `license: null` if no code license is declared.
  Do not infer an open-source license from a public repository alone.
- Omit `quality` for a server that has not received a rubric assessment.

The available categories are `data-statistics`, `geospatial`, `legal-tech`,
`government-public-finance`, `public-services`, `employment`, `transport`, `invoicing`,
`cybersecurity-compliance` and `design-other`. They must stay aligned across the schema,
README generator and new-server issue form.

## Maintenance commands

Use Python 3.12 (as in CI) and install `scripts/requirements.txt` in a local virtual
environment. After `source .venv/bin/activate`, run:

| Command | Purpose |
|---------|---------|
| `python3 scripts/validate_servers.py` | Validate server schemas, filenames, duplicate names and URLs |
| `python3 scripts/build_readme.py` | Regenerate README badges and tables |
| `python3 scripts/build_readme.py --check` | Check for drift without rewriting files; used in CI |
| `python3 scripts/build_catalog.py` | Generate `site/`, including `catalog.json`, both schemas and the browse page |
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | Test the static rubric, schemas and public rendering without querying external servers |

### Local preview and deployment

```bash
python3 scripts/build_catalog.py
python3 -m http.server 8000 --directory site
```

Open <http://localhost:8000/>. The site needs HTTP because it fetches `catalog.json`;
opening `index.html` as a local file is not supported. Generated `site/` is ignored by Git.

The repository maintainer must enable **Settings → Pages → Build and deployment →
GitHub Actions** before publication. The inherited `.github/workflows/pages.yml`
builds and deploys on pushes to `main`. After the workflow exists on `main` and Pages
is enabled, a maintainer can also trigger a deployment with:

```bash
gh workflow run pages.yml --repo bsab/france-mcp-servers --ref main
```

The logo is `logo.svg`. The GitHub social image source is `.github/social-preview.svg`;
keep its 1280×640 PNG in sync when changing the branding. Uploading that image in
repository settings is a separate maintainer action, not part of the Pages deployment.

## JSON catalog

After Pages is enabled and deployed, the machine-readable catalog is regenerated
on every push to `main`:

| Resource | URL |
|----------|-----|
| Catalog | <https://bsab.github.io/france-mcp-servers/catalog.json> |
| Catalog schema | <https://bsab.github.io/france-mcp-servers/schema/catalog.schema.json> |
| Server schema | <https://bsab.github.io/france-mcp-servers/schema/server.schema.json> |
| Browse page | <https://bsab.github.io/france-mcp-servers/> |

`version` identifies the document structure and changes only for incompatible
updates. Each `servers` entry contains its source fields plus `url`, the canonical
link (`repository_url`, then `site_url`, then `mcp_endpoint`), and `readiness_score`,
derived from the documentation assessment or `null` if unassessed.
`quality_rubric` exposes the shared rubric. France uses English category identifiers
in its independent catalog version 1; it does not republish the Italian catalog API.

## Static documentation assessment

The **Ready score** is a documented-readiness index from 0 to 100, not a measure of
popularity, security or runtime reliability. Assessment reads public documentation:
it does not run servers, call MCP tools or certify that instructions work.
A score is not a requirement for inclusion.

### Rubric v1

Each criterion receives `absent` (0), `partial` (half weight) or `complete` (full weight).
`absent` means **not documented in the consulted sources**, not necessarily missing
functionality. Sum the contributions without rounding: partial compatibility earns
7.5 out of 15 points.

| Criterion | Weight | Complete | Partial |
|-----------|-------:|----------|---------|
| `installation` | 30 | Concrete installation and startup commands, or remote connection steps, with no operational steps left to invent | Access or installation mentioned, but operational steps incomplete |
| `configuration` | 20 | Runtime, dependencies and prerequisites, plus required variables and credentials (or an explicit statement that none are needed) | Only some prerequisites or configuration explained |
| `tools` | 20 | MCP tools or capabilities described with at least one concrete usage example, including a prompt | Only a capability description or only an example |
| `compatibility` | 15 | Explicit MCP transport and a named client with a configuration or connection example | Only transport or client instructions; do not infer stdio from command syntax alone |
| `license` | 10 | Explicit license with accessible terms that apply to the server code | License name or badge only, without accessible terms |
| `limitations` | 5 | Concrete limitation with its impact or a workaround: unsupported operations, data coverage, read-only access, rate limits | Generic warning only, such as “experimental” or “beta” |

When none of the stated evidence is available, assign `absent` and explain why.
Keyword searches alone are insufficient: examples must concern MCP usage, not just
generic project features. Good documentation may describe a broken server, while
poor documentation may accompany a good server. The weights are an explicit catalog
choice, not a validated benchmark.

### Recording an assessment

The optional `quality` field in `servers/*.json` contains:

- `rubric_version`: `1`, explicitly identifying the method;
- `reviewed_at`: the consultation date, in `YYYY-MM-DD` format;
- `status`: `assessed` or `unassessed`;
- for `assessed`, `criteria` containing **all six** criteria in the table;
- for each criterion, `status`, at least one HTTPS `evidence` URL and original,
  specific `notes`, including when the result is `absent`.

Consult the README, relevant linked documents and license text. Prefer commit-pinned
GitHub URLs with sections or line numbers where useful, so evidence stays verifiable.
Do not copy long documentation excerpts. Existing catalog metadata is not a substitute
for the project's own sources.

This JSON fragment illustrates **one criterion**. Repeat it for all six using sources
you actually consulted; the URL here is only an example:

```json
"compatibility": {
  "status": "partial",
  "evidence": ["https://example.org/documentation#client"],
  "notes": "An MCP client configuration is provided, but the transport is not explicitly stated."
}
```

If you cannot consult enough sources, **do not assign zero**. Omit `quality` for an
unreviewed server. After an unsuccessful review attempt, instead record the reason
and attempted sources, without `criteria`:

```json
"quality": {
  "rubric_version": 1,
  "reviewed_at": "2026-09-06",
  "status": "unassessed",
  "reason": "Public documentation could not be accessed during review; a score cannot be assigned.",
  "evidence": ["https://example.org/documentation"]
}
```

Failure to retrieve sources does not prove abandonment. The date documents the
review, not the latest commit or a health check. A new assessment must revisit all
criteria and update dates, sources and notes; do not only refresh the date to make
an old review appear current.

### Scores, ordering and transparency

Shared code in [`scripts/quality.py`](scripts/quality.py) calculates the score.
**Do not enter manual scores** in server files. In the JSON catalog:

- `quality` preserves the assessment and evidence, when available;
- `readiness_score` is a number from 0 to 100, or `null` for **unassessed**;
- `quality_rubric` exposes weights and status meanings to API consumers.

README tables and the web catalog sort by descending score, then alphabetically for
ties, with unassessed entries last. Zero is a completed assessment, distinct from
no assessment. The site supports assessed/unassessed filters and name sorting.
README scores link to evidence files; site details show each criterion and review date.

Stars, `featured` and remote endpoints **do not earn points** or determine ordering.
`featured` remains an editorial selection; remote access is operational information.
Do not assign “healthy” or “stale” badges from this rubric or the latest commit date.

To correct an assessment, open a PR with sources and an explanation, or report an issue.
Changes to weights or criterion meanings require a new rubric version and reassessment
of existing entries; never silently rescore judgments made under a different method.

## Reporting problems

Report broken links, incorrect or outdated information, or unmaintained servers
through an [issue](https://github.com/bsab/france-mcp-servers/issues).
