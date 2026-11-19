# Implement the `carve` HTML renderer from its specification

## Goal

Our team writes its documentation, release notes, runbooks and meeting notes in Carve, a
lightweight markup language that started from Djot. Until now our build rendered them with the
`carve` command of carve-rs 0.1.14, the Rust implementation of the Carve 0.1.14 specification.
The build is moving into an audited environment where only code we own may run: no third-party
binaries or packages, no network, just Python, Go and Rust with their standard libraries. So we
need a renderer of our own, written from the published specification and documentation, and it
has to turn every page into exactly the HTML that carve-rs 0.1.14 produced.

Exactly means byte for byte. Our page cache and our CDN key every rendered page by the checksum
of its HTML; the review bot diffs the rendered HTML of every changed page in a pull request; and
the archive signs each published page. If a single attribute, entity, blank line or space of
indentation differs from what carve-rs wrote, every cached page is invalidated at once, reviews
fill with diffs nobody made, and the archive stops verifying. Write that renderer.

## Context

- The Carve 0.1.14 specification is in `/app/spec`: the normative grammar modules (`*.ebnf`, read
  `README.md` and `00-preamble.ebnf` first), the structured contracts they cite (`*.json`,
  `plus-ownership.crv`) and `normative-clauses.txt`, the list of normative clauses. The
  specification defines parsing, resolution and the HTML serialization (attribute order,
  escaping, indentation, sections) that our pages depend on.
- The documentation site's pages are in `/app/docs`, as Markdown source. They explain the
  language, the differences from Djot (`divergence-from-djot.md`), the engines and their
  options, and more. Where the documentation and the specification disagree, the specification
  is right. The site's example gallery and the conformance corpus are not included.
- Nobody has carve-rs, another Carve engine, a test suite or a collection of rendered pages to
  give you. carve-rs 0.1.14 implements this specification, so read it closely; what its command
  line does beyond the specification is described below.
- There is no network access. Python 3.12, Go and Rust (`rustc` and `cargo`, standard library
  only) are installed, here and where your renderer will run. No Carve library or tool is
  available.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/carve`. Keep
`/app/rebuild` under 2 GB and 200,000 files and directories.

- `carve [--safe] [--html] [FILE]` renders the Carve document FILE, or standard input when FILE
  is missing or `-`, to HTML on standard output and exits 0. The options may come before or
  after FILE. It writes what carve-rs 0.1.14's `carve` writes for the same arguments and input:
  the document's HTML exactly as the specification serializes it, followed by one newline (an
  empty document gives just the newline).
- It renders the way carve-rs's command line does when given no options: HTML (not the static,
  self-contained variant), heading sections on, smart typography on, raw `=html` content passed
  through, and only the core language (no optional extension enabled, no symbol map, no mention
  or tag links).
- `--safe` is the setting for untrusted input: raw `=html` blocks and spans are escaped instead
  of passed through, as the specification describes, and include directives stay literal text.
  `--html` asks for HTML output, which is already the default.
- Input is read as UTF-8 and normalized as the specification says (PART 0): a leading byte order
  mark is dropped, ill-formed UTF-8 and NUL become U+FFFD, and `\r\n` and `\r` end a line as
  `\n` does.
- Errors: a FILE that cannot be read (missing, a directory), more than one FILE, or an unknown
  option (an argument that starts with `-` and is none of the above; `--` is one too) makes
  `carve` exit with status 2 and write nothing to standard output. Nothing of ours reads
  standard error, so what you write there is up to you.
- Everything it needs at run time is inside `/app/rebuild`, apart from the tools listed above.
- Out of scope: include directives (`{{ path }}`; our pages have none), the other `carve`
  commands (`fmt`, `lint`, `flatten`, `region`, `merge`, `trace`, `migrate`), every output
  other than HTML (Markdown, plain text, ANSI, canonical Carve, the AST as JSON), the importers,
  every other option (static mode, extensions, profiles, symbols, smart-typography modes, quote
  locales, mention and tag links, source lines, sections off, loss reports, include limits),
  `--help` and `--version`.
- Where it will be used, it runs as an unprivileged user that cannot write to `/app/rebuild`.
  Each run starts in a new working directory that holds only that run's files, with `HOME` and
  `TMPDIR` set to new empty directories and nothing left from earlier runs anywhere it can
  write. Its environment holds only `PATH=/usr/local/bin:/usr/bin:/bin`, `LANG` and `LC_ALL` set
  to `C.UTF-8`, `TERM=dumb`, `NO_COLOR=1`, `HOME` and `TMPDIR`; its standard input, output and
  error are pipes, never a terminal. It gets an 8 MB stack, at most 512 processes, files of at
  most 256 MB and no core files.
- Each run finishes within 2 seconds, which is what our build gives one page, uses at most 4 GB
  of memory, and adds at most 1 GB and 100,000 files and directories to the disk; carve-rs takes
  a few milliseconds per page.
- We will maintain this code for years: keep it modular, with reading the source and its block
  layout, inline parsing, resolution (references, footnotes, numbering), HTML serialization and
  the command line in separate parts.

## Completion

The work is complete when your `carve` cannot be told apart from carve-rs 0.1.14's by what it
prints on standard output and how it exits, for any page we render. Keep `/app/rebuild/carve`
runnable at all times.
