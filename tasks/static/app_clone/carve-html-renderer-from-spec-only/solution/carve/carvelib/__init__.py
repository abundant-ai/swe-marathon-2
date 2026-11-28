"""A renderer for Carve 0.1.14, written from its specification: Carve markup
in, the specification's HTML serialization out.

Modules:
  source     - input decoding and normalization (PART 0 INPUT)
  chars      - character classes and label keys used by the grammar
  attrs      - attribute block parsing and merging (PART 4)
  nodes      - block and inline node classes
  blocks     - block layout parser (PART 0, PART 2, PART 9 block clauses)
  inline     - inline parser (PART 3, PART 9 §9)
  typography - mentions, tags, symbols and smart typography passes
  tables     - pipe tables and delimited CSV/TSV bodies (PART 9 §5)
  resolve    - document-wide resolution (PART 9R)
  html       - HTML serialization (PART 10)
  htmlattrs  - escaping and attribute hardening (PART 9 §25)
  render     - the pipeline from source text to HTML
  cli        - command line
"""
