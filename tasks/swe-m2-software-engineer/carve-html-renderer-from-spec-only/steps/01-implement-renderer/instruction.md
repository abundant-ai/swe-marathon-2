# Implement the `carve` HTML renderer from its specification

## Goal

Every team in our company writes its pages in Carve, a lightweight markup language that started
from Djot: documentation and handbooks, release notes and reports, runbooks, postmortems and
meeting notes. Until last month a hosted service rendered them for us with the `carve` command of
carve-rs 0.1.14, the Rust implementation of the Carve 0.1.14 specification. Our audit then moved
the build into an environment where nothing runs but code our own team wrote and the approved
toolchains, Python 3.12, Go and Rust with their standard libraries: no third-party binaries or
packages, and no network. So we need a renderer of our own, written from the published
specification and documentation, that turns every page into exactly the HTML that carve-rs 0.1.14
produced.

Many people have written those pages over the years, and between them they use all of the core
language, nested in every way it allows: inline markup and attributes, lists, block quotes and
fences, tables, definition lists, admonitions, references, footnotes and captions, comments and
raw HTML. Pages also keep their writers' slips (markup left open, stray brackets, half-finished
edits, odd indentation), and carve-rs rendered those as well. A page like that has to come out
exactly as carve-rs wrote it, the same as a tidy one.

Exactly means byte for byte. Our page cache and our CDN key every rendered page by the checksum of
its HTML; the archive signs each published page and verifies it by rendering its committed source
again and checking the result against the signature. A renderer that writes even one attribute,
entity, blank line or space of indentation differently from carve-rs changes the checksum of every
page that has it: the cache and the CDN drop all of those pages at once, and the archive's checks
fail on pages nobody touched. Write that renderer.

## Context

- The Carve 0.1.14 specification is in `/app/spec`: the normative grammar modules (`*.ebnf`, read
  `README.md` and `00-preamble.ebnf` first), the structured contracts they cite (`*.json`,
  `plus-ownership.crv`) and `normative-clauses.txt`, the list of normative clauses. The
  specification defines parsing, resolution and the HTML serialization (attribute order,
  escaping, indentation, sections) that our pages depend on.
- The documentation site's pages are in `/app/docs`, as Markdown source. They explain the
  language, the differences from Djot (`divergence-from-djot.md`), the engines and their
  options, and more. Where the documentation and the specification disagree, the specification
  is right.
- The audit admits the specification and these documentation pages as references and nothing else
  from outside: no third-party program and no output of one. So carve-rs (its builds and its
  source), the other Carve engines, upstream's conformance corpus, example gallery and pack, and
  its executable model were not reviewed and are not here, although the documentation mentions
  them; they may not be brought in. Many of our pages hold customer and incident details, so
  neither they nor the HTML rendered from them leaves the production build, and we never ran
  carve-rs ourselves. carve-rs 0.1.14 implements this specification, so read it closely; what its
  command line does beyond the specification is described below.
- There is no network access. Python 3.12, Go and Rust (`rustc` and `cargo`, standard library
  only) are installed, here and where your renderer will run; use whichever you prefer, since we
  maintain all three. No Carve library or tool is available.

## What to deliver

Your implementation in `/app/rebuild`, with an executable `/app/rebuild/carve`. We install
`/app/rebuild` on the build machines as one directory, so keep it
under 2 GB and 200,000 files and directories.

- `carve [--safe] [--html] [FILE]` renders the Carve document FILE, or standard input when FILE
  is missing or `-`, to HTML on standard output and exits 0. The options may come before or
  after FILE. It writes what carve-rs 0.1.14's `carve` writes for the same arguments and input:
  the document's HTML exactly as the specification serializes it, followed by one newline (an
  empty document gives just the newline).
- It renders the way carve-rs's command line does when given no options: HTML (not the static,
  self-contained variant), heading sections on, smart typography on, raw `=html` content passed
  through, and only the core language (no optional extension enabled, no symbol map, no mention
  or tag links).
- We render pages from outside contributors and text pasted out of tickets with `--safe`, the
  setting for untrusted input: raw `=html` blocks and spans are escaped instead of passed through,
  as the specification describes, and include directives stay literal text. Some older build
  scripts still pass `--html`, which asks for HTML output, the default anyway.
- Input is read as UTF-8 and normalized as the specification says (PART 0): a leading byte order
  mark is dropped, ill-formed UTF-8 and NUL become U+FFFD, and `\r\n` and `\r` end a line as
  `\n` does.
- Errors: our build acts on the exit status. carve-rs exits with status 2 and writes nothing to
  standard output when FILE cannot be read (it is missing or a directory), when there is more
  than one FILE, and when an argument that starts with `-` is not an option it knows; it counts
  `--` as one of those, not as the end of the options. Our build passes no option but `--safe`
  and `--html`, so yours may answer every other argument that starts with `-` (apart from `-`
  itself) the same way. Nothing of ours reads standard error, so what you write there is up to
  you.
- Everything it needs at run time is inside `/app/rebuild`, apart from the tools listed above.
- Out of scope: include directives (`{{ path }}`; our pages have none), the other `carve`
  commands (`fmt`, `lint`, `flatten`, `region`, `merge`, `trace`, `migrate`), every output
  other than HTML (Markdown, plain text, ANSI, canonical Carve, the AST as JSON), the importers,
  every other option (static mode, extensions, profiles, symbols, smart-typography modes, quote
  locales, mention and tag links, source lines, sections off, loss reports, include limits),
  `--help` and `--version`.
- Our build renders each page in a sandbox of its own. `carve` runs there as an unprivileged user
  that cannot write to `/app/rebuild`, in a new working directory that holds only that page's
  files, with `HOME` and `TMPDIR` set to new empty directories; nothing one render leaves behind
  is still there for the next. Its environment holds only `PATH=/usr/local/bin:/usr/bin:/bin`,
  `LANG` and `LC_ALL` set to `C.UTF-8`, `TERM=dumb`, `NO_COLOR=1`, `HOME` and `TMPDIR`; its
  standard input and output are pipes, never a terminal, and its standard error is discarded. The
  sandbox allows an 8 MB stack, at most 512 processes and threads, files of at most 256 MB and no
  core files.
- Each run finishes within 2 seconds, which is what our build gives one page, uses at most 4 GB
  of memory, and adds at most 1 GB and 100,000 files and directories to the disk; carve-rs took a
  few milliseconds per page.
- We will maintain this code for years: keep it modular, with reading the source and its block
  layout, inline parsing, resolution (references, footnotes, numbering), HTML serialization and
  the command line in separate parts.

## Completion

The work is complete when your `carve` cannot be told apart from carve-rs 0.1.14's by what it
prints on standard output and how it exits, for any page we render and any of the command lines
above. Every page it renders exactly is one we can move over, so keep `/app/rebuild/carve`
runnable at all times.
