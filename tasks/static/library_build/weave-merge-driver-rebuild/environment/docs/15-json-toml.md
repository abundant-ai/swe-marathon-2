# 15. JSON and TOML

JSON and TOML files take the same routes, entity merge and checks as code.

## 15.1 Definitions and loading

- **[DATA-1] Definitions.** sem-core registers its JSON and TOML readers whatever features are
  enabled; they give the definitions of [ENT-1]: for orientation, the members of a root JSON object
  (named by their keys), the elements of a root array (`0`, `1`, ...), or else one `chunk` named
  `(document)`; and the root keys, `[table]` sections and `[[array]]` entries (`array/0`, ...) of a
  TOML text that parses (one that does not parse has none).
- **[DATA-2] Loads.** This is *loads* in [ROUTE-8], [GATE-DATA-1] and [GATE-DATA-2]. TOML loads when
  `toml` 0.8.23 parses it as a table (`str::parse::<toml::Table>`); a key stated twice in one table
  fails. JSON loads when it is whitespace and comments (`//` to the line's end, `/* */`, an unclosed
  `/*` running to the end), at most one value, then only whitespace and comments; an empty text
  loads. A value is an object (`{`, members `"key"` `:` value separated by `,`, a `,` before `}`
  allowed, `}`), an array (likewise with `]`), a string (`"` to the next unescaped `"`, `\` skipping
  a byte; a raw newline or the end fails), or a token starting with `-` or an ASCII letter or digit
  and continuing with letters, digits, `+`, `-`, `.`: a number when it starts with `-` or a digit,
  else it must be `true`, `false` or `null`. A leading byte-order mark fails, as does nesting deeper
  than 256. A key is its raw bytes between the quotes. Its *tally* at a path (the keys above it, all
  elements of an array sharing one path) is the most times one object at that path states it.

## 15.2 Values

- **[DATA-3] Values.** For the rules below a version's *value* is its strict reading: JSON by
  `serde_json`, TOML by `toml::from_str` into a `toml::Value` made a `serde_json::Value`. A version
  without one stops the rule.
- **[DATA-4] Merging values.** BASE, OURS, THEIRS (a missing key being a value too) merge to OURS'
  if OURS equals THEIRS, THEIRS' if OURS equals BASE, OURS' if THEIRS equals BASE; else, two objects
  (BASE an object or missing) merge key by key, keys whose merge is missing left out; else two
  arrays of strings, numbers and booleans (BASE's alike or missing), under a path containing one of
  the keys `dependencies`, `optional-dependencies`, `dependency-groups`, `dev-dependencies`,
  `build-dependencies`, `requires`, `features`, `keywords`, `categories`, `classifiers`, `members`,
  `workspaces`, `files`, `include`, `exclude`, `ignore`, `ignorePatterns`, `lib` or `types`, merge
  to the items of BASE, OURS and THEIRS in that order, once each, less every BASE item one side
  removed (in `pyproject.toml`, two items naming one package conflict: the name is the leading run,
  after trimming, of ASCII letters, digits, `_`, `.`, `-`, lower-cased, `_` and `.` made `-`);
  anything else conflicts. A value *agrees* with a merged value when objects have the same keys with
  agreeing values, such arrays hold the same items as text, none twice, other arrays have agreeing
  items pairwise, and anything else is equal.
- **[DATA-5] Value carried** ([RULE-DATA]). OURS, THEIRS and, unless blank, BASE need values whose
  merge does not conflict. OURS is taken when its value agrees with the merge and no line THEIRS
  wrote or removed (in `diffy`'s zero-context patch from BASE) holds a comment outside quotes (`//`,
  `/*` or `*/` in JSON; `#` in TOML); THEIRS likewise. Both: the byte-wise smaller text; one: that
  text.
- **[DATA-6] Key union** ([RULE-DATA-UNION]), BASE not empty. Each side keeps every BASE line of the
  region in order, exactly or with a comma added at its end (lines aligned without trailing commas);
  its other lines are runs after the BASE line they follow, or before all. Both sides need runs. The
  answer walks the places, writing each BASE line in OURS' spelling if that has a trailing comma,
  else THEIRS'. One run, or two equal runs, stand. Two different runs need a non-blank line each and
  may share no line (non-blank lines trimmed, without trailing comma); the run whose lines so read,
  joined by `\n`, sort first goes first (OURS' on a tie); their last non-blank lines must agree on a
  trailing comma; if neither has one and the first non-blank BASE line after the place (past the
  region, the first non-blank line before the next region) starts with `]` or `}`, the first run's
  last non-blank line becomes its text trimmed at the end, `,` and its line ending (a comment on it
  means no union). The answer is only a candidate: all four texts need values, and the answer's must
  agree with the merge ([DATA-4]).
