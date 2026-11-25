<!-- https://doc.openfoam.com/2606/contributing/how-to -->

# How to contribute

This guide covers authoring for the Docusaurus site. Edit `docs/` and open merge
requests on the default branch.

## Local setup

```
npm install
npm start

```

Open <http://localhost:3000/2606/> (home page at `/2606/`).

Production\-style preview:

```
npm run build
npm run serve

```

## Adding or editing pages

1. Edit Markdown under `docs/`, matching the folder structure used on
[doc.openfoam.com](../index.md).
2. Use standard Markdown. Prefer **relative links** to other docs pages:
`[fvSchemes](../fundamentals/case-structure/fvschemes)`.
3. For API links, prefer the release\-relative form — the API version is
expanded at build time from `config/openfoam-release.json`:

```
[Foam::functionObjects::DESModelRegions](openfoam-api:Foam_functionObjects_DESModelRegions)
[Source documentation](openfoam-api:grpTurbulence)

```

Bulk\-convert existing API URLs:

```
python3 scripts/migrate-api-links.py --write

```
4. For openfoam.com links (release history, homepage, etc.), use `openfoam-site:` —
the site base URL is expanded at build time from the same config:

```
[v1612+](openfoam-site:news/main-news/openfoam-v1612+)
[OpenCFD Ltd.](openfoam-site:)

```

Bulk\-convert existing site URLs:

```
python3 scripts/migrate-site-links.py --write

```
5. For source\-code links, prefer `openfoam-code:` — expanded at build time to
the configured GitLab repo (`code` in `config/openfoam-release.json`,
default `https://gitlab.com/openfoam/core/openfoam`):

```
[DESModelRegions](openfoam-code:src/functionObjects/field/DESModelRegions)
[fullCase](openfoam-code:tutorials/incompressible/pimpleFoam/LES/surfaceMountedCube/fullCase)

```

Override locally with `OPENFOAM_RELEASE`, `OPENFOAM_API`, `OPENFOAM_SITE`, or
`OPENFOAM_CODE_REPO`, or edit `config/openfoam-release.json`. Full tree URLs
must use the configured ref (`OpenFOAM-v2606` today).

Bulk\-convert existing GitLab URLs:

```
python3 scripts/migrate-gitlab-links.py --write

```
6. Set `sidebar_position` in front matter to control order within a folder.

## Workflow before merge

Run local CI before opening a merge request:

```
ofr v2606
scripts/run-ci.sh --strict

```

## Citations

1. Add a BibTeX entry to [`assets/openfoam.bib`](/2606/assets/files/openfoam-ffd296b3c97aadd35ce5d5a8b2b7f742.bib).
2. Cite it in Markdown with a **key only** (numbers are assigned automatically):

```
Based on *Launder and Spalding* [@cite launder_numerical_1974].

```
3. `npm run build` runs `build-citations.py` first, which updates
`data/citations.json` and the [References](../references.md) page.

## Assertions

Document claims about tutorials, source files, and paths can be checked in CI with
assertion comments (removed from the published site at compile time).

```
<!-- @assert functionObject incompressible/pimpleFoam/RAS/propeller forces -->
<!-- @assert patchType compressible/acousticFoam/obliqueAirJet acousticWaveTransmissive -->
<!-- @assert path $FOAM_TUTORIALS/incompressible/pimpleFoam/RAS/propeller -->

```

With OpenFOAM sourced (`ofr v2606`):

```
npm run validate-asserts

```

API link validation downloads `OpenFOAM-api.tags-2606` automatically (see
`scripts/fetch-api-tags.sh`). Override with `OPENFOAM_API_TAGS_URL` if needed.

## Math

OpenFOAM macros (`\u`, `\grad`, `\div`, etc.) are defined in `config/katex-macros.ts`.

## Repository layout

| Path | Purpose |
| --- | --- |
| `docs/` | Docusaurus Markdown — **edit here for 2606 docs** |
| `static/img/` | Figures referenced as `/img/...` in Markdown |
| `assets/` | Bibliography (`openfoam.bib`) and licenses |
| `scripts/` | Validators and deploy helpers |

RTM hub bullet lists read `group` and optional `menu_id` from page front matter in
`docs/`. Regenerate with `python3 scripts/generate-rtm-index.py --write` (also run
in CI).

Optional one\-off migration tools live in `scripts-legacy/` (for example
`convert-from-nanoc.py`, `sync-rtm-groups.py`). They are not used for normal
authoring or CI.
