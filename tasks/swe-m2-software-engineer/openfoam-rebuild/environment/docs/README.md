# OpenFOAM v2606 documentation

Published documentation of the installed OpenFOAM, unchanged apart from format (PDF pages are
also given as plain text, and web pages as Markdown).

| Folder | What it is | Source |
|---|---|---|
| `guides/` | User Guide, Tutorial Guide and Programmer's Guide, each as PDF and plain text | dl.openfoam.com/source/v2606 |
| `website/` | The v2606 documentation site: case files, input types, tools, boundary conditions, function objects, models, schemes, tutorials and examples; one Markdown file per page, in the site's folders (`index.md` is the front page) | doc.openfoam.com/2606 |
| `release-notes-v2606.md` | What is new in v2606 | openfoam.com/news/main-news/openfoam-v2606 |
| `repository/` | The documentation files in OpenFOAM's source repository at v2606: README, build notes, requirements, the `openfoam` man page, licence, contributors | gitlab.com/openfoam/core/openfoam, tag OpenFOAM-v2606 |

Each program also describes itself: `<program> -help` and `-help-full`, and options such as
`-listScalarBCs` or `-listFunctionObjects`. The tutorials are in `/app/tutorials`.

Licences: the guides are © OpenCFD Ltd, CC BY-NC-ND 3.0; the website is © OpenCFD Ltd,
CC BY-NC-ND 4.0; OpenFOAM and the repository files are GPL-3.0 (`repository/LICENSE.md`).
