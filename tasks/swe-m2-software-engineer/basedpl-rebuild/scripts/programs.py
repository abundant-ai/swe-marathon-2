"""New BPL programs for the private cases, written for this task, with data chosen by the seed.

Used by scripts/make_cases.py (`program_cases` for the "program" kind, `display_cases` for part of
the "display" kind). Each template is the kind of small program people write in an array
language: a report over a table, a text tool reading standard input, a validator that reports
what went wrong, a numeric routine, a module and the program that loads it. The templates are
public with the generator; the data (names, numbers, sizes of tables, words, the input text) come
from the private seed, so the answers are not. Nothing here runs BPL: the answers are recorded
from the original when the verifier image is built.
"""

from __future__ import annotations

import json
import random

PLACES = ["north", "south", "east", "west", "harbor", "valley", "ridge", "delta", "summit", "meadow", "coast", "plains"]
PEOPLE = ["Ada", "Bo", "Cy", "Di", "Eve", "Finn", "Gus", "Hana", "Ivo", "Jo", "Kai", "Lin", "Mo", "Nia", "Otto", "Pia"]
ITEMS = ["bolt", "nut", "washer", "hinge", "spring", "valve", "gasket", "bearing", "pulley", "clamp", "rivet", "bracket"]
TEXT_WORDS = ("the a an of and to in is on at by for with river stone light green paper quiet market garden window "
              "morning evening winter summer train road bridge field cloud rain wind small large old new early late "
              "bright dark open closed simple careful steady slow quick table chair letter number story").split()


def bpl_strings(words: list[str]) -> str:
    """A BPL strand of string literals: `"a" "b" "c"` (a vector of strings, even of one)."""
    if len(words) == 1:
        return f'[{json.dumps(words[0])}]'
    return " ".join('"' + word.replace('"', '""') + '"' for word in words)


def bpl_numbers(values: list[float | int]) -> str:
    """A BPL strand of numbers with `¯` for negatives (bracketed when it has one item)."""
    text = " ".join(("¯" + str(abs(value))) if value < 0 else str(value) for value in values)
    return f"[{text}]" if len(values) == 1 else text


def money(rng: random.Random, low: float, high: float) -> float:
    """An amount with at most two decimal places, between `low` and `high`."""
    return round(rng.uniform(low, high) * 4) / 4


def sales_report(rng: random.Random) -> dict:
    """Revenue by region: totals per region with Key, the best region, each region's share in
    whole percent, and the totals with two decimals."""
    regions = rng.sample(PLACES, rng.randint(3, 5))
    rows = rng.randint(6, 14)
    region = [rng.choice(regions) for _ in range(rows)]
    units = [rng.randint(1, 30) for _ in range(rows)]
    price = [money(rng, 1, 25) for _ in range(rows)]
    program = f"""⍝ Revenue by region for the week
region←{bpl_strings(region)}
units←{bpl_numbers(units)}
price←{bpl_numbers(price)}
revenue←units×price
names←∪region
totals←region {{+/ω}}⌸ revenue
order←⍒totals
⎕←"best region: ",(↑order)⊃names
report←{{α,": ",⍕ω}}
⎕←names report¨ totals
⎕←"share: ",⍕⌊0.5+100×totals÷+/totals
⎕←2⍕totals
⎕←"rows over 50: ",⍕+/revenue>50
"""
    return {"files": {"sales.bpl": program}, "argv": ["sales.bpl"]}


def grade_book(rng: random.Random) -> dict:
    """Term grades: each student's mean over the tests, a letter by interval index, the class
    average, the top student, and the best score of each test."""
    count, tests = rng.randint(3, 7), rng.randint(2, 5)
    students = rng.sample(PEOPLE, count)
    scores = [rng.randint(35, 100) for _ in range(count * tests)]
    cutoffs = sorted(rng.sample([55, 60, 65, 70, 75, 80, 85, 90], 4))
    program = f"""students←{bpl_strings(students)}
scores←{count} {tests}ρ{bpl_numbers(scores)}
mean←+/÷≢
avg←mean⍤1⁝scores
grade←{{"FDCBA"⊃⍨{bpl_numbers(cutoffs)}⍸ω}}
⎕←students,¨(⊂": "),¨grade¨avg
⎕←"class average: ",1⍕mean avg
⎕←"top: ",(↑⍒avg)⊃students
⎕←"passed: ",⍕+/avg≥{cutoffs[0]}
⎕←⌈⌿scores
avg
"""
    return {"files": {"grades.bpl": program}, "argv": ["grades.bpl"]}


def word_count(rng: random.Random) -> dict:
    """A word counter reading text on standard input: the number of words, the distinct words,
    and the most frequent ones with their counts."""
    lines = [" ".join(rng.choice(TEXT_WORDS) for _ in range(rng.randint(3, 10))) for _ in range(rng.randint(2, 6))]
    top = rng.randint(2, 5)
    program = f"""text←•nget "-"
words←((text≠' ')∧text≠•ucs 10)⊆text
⎕←"words: ",⍕≢words
uniq←∪words
counts←words {{≢ω}}⌸ ι≢words
⎕←"distinct: ",⍕≢uniq
order←⍒counts
⎕←{top}↑order⊃¨⊂uniq
⎕←{top}↑order⊃¨⊂counts
⎕←"longest: ",(↑⍒≢¨uniq)⊃uniq
"""
    return {"files": {"count.bpl": program}, "argv": ["count.bpl"], "stdin": "\n".join(lines) + "\n"}


def run_lengths(rng: random.Random) -> dict:
    """Run-length encoding of a line of text with `#`'s monad, the encoding written as count and
    character pairs, and the decoding checked against the original."""
    text = "".join(rng.choice("abcxyz") * rng.randint(1, 5) for _ in range(rng.randint(4, 9)))
    program = f"""line←"{text}"
runs←#line
[lengths letters]←runs
⎕←lengths
⎕←letters
⎕←∊({{⍬⍕ω}}¨lengths),¨letters
⎕←"longest run: ",⍕⌈/lengths
⎕←line≡#⁻runs
"""
    return {"files": {"rle.bpl": program}, "argv": ["rle.bpl"]}


def ledger(rng: random.Random) -> dict:
    """A bank statement: running balance with a scan, the days the account was overdrawn, the
    largest withdrawal, and statement lines with fixed-width amounts."""
    opening = money(rng, 20, 400)
    days = rng.randint(5, 12)
    moves = [money(rng, -150, 160) for _ in range(days)]
    program = f"""opening←{bpl_numbers([opening])}
moves←{bpl_numbers(moves)}
balance←opening+(+\\moves)
⎕←balance
⎕←"overdrawn on days: ",⍕⍸balance<0
⎕←"largest withdrawal: ",2⍕|⌊/moves
lines←(10 2⍕moves),(⊂" -> "),¨10 2⍕balance
⎕←"closing: ",2⍕¯1↑balance
"""
    return {"files": {"statement.bpl": program}, "argv": ["statement.bpl"]}


def temperatures(rng: random.Random) -> dict:
    """A conversion table: Celsius readings to Fahrenheit and Kelvin, the mean and range, and
    the table formatted to one decimal place."""
    readings = [round(rng.uniform(-15, 38), 1) for _ in range(rng.randint(4, 9))]
    program = f"""celsius←{bpl_numbers(readings)}
fahrenheit←32+celsius×9÷5
kelvin←celsius+273.15
table←celsius,fahrenheit,⍪kelvin
⎕←8 1⍕⍉3 {len(readings)}ρcelsius,fahrenheit,kelvin
⎕←"mean: ",⍕(+/÷≢)celsius
⎕←"range: ",⍕(⌈/celsius)-⌊/celsius
⎕←"freezing: ",⍕+/celsius≤0
"""
    return {"files": {"convert.bpl": program}, "argv": ["convert.bpl"]}


def primes(rng: random.Random) -> dict:
    """Number theory on a few seeded numbers: their prime factors, greatest common divisor and
    least common multiple, and the primes up to a bound."""
    numbers = [rng.randint(12, 5000) for _ in range(rng.randint(3, 5))]
    bound = rng.randint(5, 25)
    program = f"""numbers←{bpl_numbers(numbers)}ₓ
⎕←⨸¨numbers
⎕←∨/numbers
⎕←∧/numbers
⎕←⍭ι{bound}
⎕←+/⍭ι{bound}
"""
    return {"files": {"numbers.bpl": program}, "argv": ["numbers.bpl"]}


def matrices(rng: random.Random) -> dict:
    """Small matrix algebra: a product, a transpose, a solve with `⌹` rounded to four places,
    and whether the product is symmetric."""
    size = rng.randint(2, 4)
    a = [rng.randint(-5, 9) for _ in range(size * size)]
    b = [rng.randint(-4, 8) for _ in range(size)]
    program = f"""A←{size} {size}ρ{bpl_numbers(a)}
b←{bpl_numbers(b)}
⎕←A+.×A
⎕←⍉A
P←A+.×⍉A
⎕←P≡⍉P
⎕←4⍕b⌹A
⎕←+/,A×A
"""
    return {"files": {"matrix.bpl": program}, "argv": ["matrix.bpl"]}


def histogram(rng: random.Random) -> dict:
    """A text histogram: one row of `*` per bucket, labels padded to one width, and the counts
    drawn from data by interval index."""
    values = [rng.randint(0, 99) for _ in range(rng.randint(10, 30))]
    step = rng.choice([10, 20, 25])
    program = f"""data←{bpl_numbers(values)}
edges←{step}×ι⌈100÷{step}
bucket←edges⍸data
counts←{{+/bucket=ω}}¨ι≢edges
⎕←counts
bars←{{ωρ'*'}}¨counts
⎕←(⍕¨edges),¨(⊂" | "),¨bars
"""
    return {"files": {"histogram.bpl": program}, "argv": ["histogram.bpl"]}


def cipher(rng: random.Random) -> dict:
    """A Caesar cipher: shift the letters of a message by a seeded amount, keep other characters,
    and shift back to check."""
    message = " ".join(rng.choice(TEXT_WORDS) for _ in range(rng.randint(3, 7))).upper()
    shift = rng.randint(1, 25)
    program = f"""message←"{message}"
shift←{shift}
encode←{{α {{i←$a ι ω ◇ i<26?$a.[26|i+α];ω}}¨ ω}}
secret←shift encode message
⎕←secret
⎕←(26-shift) encode secret
⎕←message≡(26-shift) encode secret
⎕←+/secret∊"AEIOU"
"""
    return {"files": {"cipher.bpl": program}, "argv": ["cipher.bpl"]}


def fibonacci(rng: random.Random) -> dict:
    """Recurrences: Fibonacci numbers by the power operator and by recursion with `∇`, exactly,
    and the ratio of consecutive terms."""
    count = rng.randint(8, 40)
    program = f"""step←{{(1↓ω),+/ω}}
⎕←↑step⍣{count}⁝0 1ₓ
fib←{{ω<2?ω;(∇ω-1)+∇ω-2}}
⎕←fib¨ι{min(count, 15)}
ratio←{{(1⊃ω)÷↑ω}}step⍣{count}⁝1 1
⎕←ratio
"""
    return {"files": {"fib.bpl": program}, "argv": ["fib.bpl"]}


def collatz(rng: random.Random) -> dict:
    """Collatz trajectories: the steps each seeded start takes to reach 1, by a power operator
    that stops on a predicate, and the longest trajectory's start."""
    starts = [rng.randint(3, 300) for _ in range(rng.randint(3, 6))]
    program = f"""next←{{(2|ω)?1+3×ω;ω÷2}}
path←{{(ω=1)?,ω;ω,∇(next ω)}}
starts←{bpl_numbers(starts)}ₓ
lengths←{{≢path ω}}¨starts
⎕←lengths
⎕←"longest from ",⍕(↑⍒lengths)⊃starts
⎕←path {min(starts)}ₓ
⎕←⌈/path {max(starts)}ₓ
"""
    return {"files": {"collatz.bpl": program}, "argv": ["collatz.bpl"]}


def validator(rng: random.Random) -> dict:
    """An order validator: each order is checked by a dfn that signals a named error for a bad
    quantity, price or code; a guard reports each failure's kind and message, and the good
    orders' total."""
    count = rng.randint(4, 8)
    codes = [rng.choice(["A1", "B7", "C3", "ZZ", "", "Q9"]) for _ in range(count)]
    quantities = [rng.randint(-3, 12) for _ in range(count)]
    prices = [money(rng, -2, 30) for _ in range(count)]
    program = f"""codes←{bpl_strings(codes)}
quantity←{bpl_numbers(quantities)}
price←{bpl_numbers(prices)}
check←{{
  c←α ◇ [q p]←ω
  0=≢c?"missing code" •signal "ORDER";
  q≤0?("quantity ",⍕q) •signal "QUANTITY";
  p<0?"negative price" •signal "PRICE";
  q×p
}}
safe←{{∞::$e.kind,": ",$e.message ◇ α check ω}}
results←codes safe¨ quantity {{α ω}}¨ price
⎕←results
good←{{0=≡ω}}¨results
⎕←"good orders: ",⍕+/good
⎕←"total: ",2⍕+/good#results
"""
    return {"files": {"orders.bpl": program}, "argv": ["orders.bpl"]}


def inventory(rng: random.Random) -> dict:
    """An inventory as keyed vectors: stock and reorder levels by item, the items to reorder,
    the order quantities, and a record of each item's status."""
    items = rng.sample(ITEMS, rng.randint(3, 7))
    stock = [rng.randint(0, 60) for _ in items]
    level = [rng.randint(5, 30) for _ in items]
    program = f"""items←{bpl_strings(items)}
stock←items:{bpl_numbers(stock)}
level←items:{bpl_numbers(level)}
low←stock<level
⎕←low
⎕←⍸low
⎕←(2×level)-stock
status←{{ω?"reorder";"ok"}}¨low
⎕←items:status
⎕←+/stock
"""
    return {"files": {"stock.bpl": program}, "argv": ["stock.bpl"]}


def rationals(rng: random.Random) -> dict:
    """Exact arithmetic: harmonic numbers as rationals, an exact mean, a continued fraction
    expansion, and the same values approximate."""
    count = rng.randint(3, 12)
    num, den = rng.randint(10, 400), rng.randint(3, 90)
    program = f"""h←+/÷1ᵣ+ι{count}
⎕←h
⎕←⌊h
values←{bpl_numbers([rng.randint(1, 50) for _ in range(rng.randint(3, 6))])}ᵣ
⎕←(+/values)÷≢values
cf←{{ω=⌊ω?,⌊ω;(⌊ω),∇÷ω-⌊ω}}
⎕←cf {num}ᵣ÷{den}ᵣ
⎕←{num}÷{den}
"""
    return {"files": {"exact.bpl": program}, "argv": ["exact.bpl"]}


def complex_roots(rng: random.Random) -> dict:
    """Complex numbers: the n-th roots of unity, their sum and product rounded, magnitudes, and a
    polynomial's values at them."""
    n = rng.randint(3, 8)
    coefficients = [rng.randint(-4, 6) for _ in range(rng.randint(2, 4))]
    program = f"""n←{n}
roots←*0j2×π(ιn)÷n
⎕←4⍕|roots
⎕←0.000001>|+/roots
⎕←{bpl_numbers(coefficients)}⌻2
⎕←|{bpl_numbers(coefficients)}⌻roots
"""
    return {"files": {"roots.bpl": program}, "argv": ["roots.bpl"]}


def newton(rng: random.Random) -> dict:
    """Square roots by Newton's method: a fixed point of the update with `⍣≡`, the number of
    steps with a history, and the error against `√` at two precisions."""
    targets = [rng.randint(2, 900) for _ in range(rng.randint(2, 5))]
    program = f"""targets←{bpl_numbers(targets)}
update←{{0.5×ω+α÷ω}}
roots←{{ω update⍣≡ ω}}¨targets
⎕←roots
•prefs ["prec":15]
⎕←roots
⎕←roots-√targets
"""
    return {"files": {"newton.bpl": program}, "argv": ["newton.bpl"]}


def text_tools(rng: random.Random) -> dict:
    """String utilities: trim and split a line on commas, join with another separator, upper and
    lower case, and a regular-expression replace."""
    fields = [" " * rng.randint(0, 2) + rng.choice(TEXT_WORDS) + " " * rng.randint(0, 2) for _ in range(rng.randint(3, 6))]
    line = ",".join(fields)
    program = f"""line←"{line}"
fields←(line≠',')⊆line
trimmed←{{((∨\\ω≠' ')∧⌽∨\\⌽ω≠' ')#ω}}¨fields
⎕←trimmed
⎕←≢¨trimmed
⎕←2↓∊(⊂"; "),¨trimmed
⎕←1 •c ∊trimmed
⎕←line •replace ["[aeiou]" "-"]
⎕←(≢¨trimmed)⌷¨⊂"short" "medium" "long"
"""
    return {"files": {"fields.bpl": program}, "argv": ["fields.bpl"]}


def csv_report(rng: random.Random) -> dict:
    """A CSV filter reading standard input: parse it with `•csv`, total a column, average another
    by group, and list the rows over a threshold."""
    groups = rng.sample(PLACES, rng.randint(2, 4))
    rows = [(rng.choice(ITEMS), rng.choice(groups), rng.randint(1, 40), money(rng, 1, 20)) for _ in range(rng.randint(4, 10))]
    data = "item,site,qty,cost\n" + "".join(f"{item},{site},{qty},{cost}\n" for item, site, qty, cost in rows)
    threshold = rng.randint(5, 30)
    program = f"""t←•csv •nget "-"
⎕←+/t.qty
⎕←t.site {{(+/÷≢)ω}}⌸ t.cost
⎕←(t.qty>{threshold})#t.item
⎕←≢t.item
"""
    return {"files": {"report.bpl": program}, "argv": ["report.bpl"], "stdin": data}


def json_transform(rng: random.Random) -> dict:
    """A JSON transform reading standard input: parse a list of objects with `•json`, compute a
    field, filter, and write JSON back with `•json⁻`."""
    records = [{"name": rng.choice(PEOPLE), "hours": rng.randint(1, 50), "rate": money(rng, 8, 40)}
               for _ in range(rng.randint(2, 6))]
    program = """r←•json •nget "-"
pay←{ω.hours×ω.rate}¨r
⎕←pay
⎕←+/pay
⎕←•json⁻ {["name":ω.name "pay":ω.hours×ω.rate]}¨r
"""
    return {"files": {"pay.bpl": program}, "argv": ["pay.bpl"], "stdin": json.dumps(records) + "\n"}


def base_conversion(rng: random.Random) -> dict:
    """Number bases: numbers in binary with `⊤`, back with `⊥`, as hexadecimal text, and the
    count of set bits with bitwise lifting."""
    numbers = [rng.randint(1, 4000) for _ in range(rng.randint(3, 6))]
    program = f"""n←{bpl_numbers(numbers)}ₓ
bits←(12ρ2)⊤n
⎕←bits
⎕←2⊥bits
hex←{{"0123456789ABCDEF".[(4ρ16)⊤ω]}}¨n
⎕←hex
⎕←+/bits
⎕←n∧ᵇ255
"""
    return {"files": {"bases.bpl": program}, "argv": ["bases.bpl"]}


def moving_average(rng: random.Random) -> dict:
    """A moving average over daily readings with windows (`↕`), the days above the average, and
    the largest rise between consecutive days."""
    values = [rng.randint(10, 99) for _ in range(rng.randint(7, 16))]
    width = rng.randint(2, 4)
    program = f"""readings←{bpl_numbers(values)}
smooth←(+/÷≢)⍤1⁝{width}↕readings
⎕←2⍕smooth
⎕←⍸readings>(+/÷≢)readings
⎕←⌈/-/⍤1⁝⌽⍤1⁝2↕readings
"""
    return {"files": {"smooth.bpl": program}, "argv": ["smooth.bpl"]}


def tournament(rng: random.Random) -> dict:
    """Match results in a table: points per team from a results matrix, the standings by grade,
    and the head-to-head record of the top two teams."""
    teams = rng.sample(PEOPLE, rng.randint(3, 6))
    n = len(teams)
    goals = [rng.randint(0, 5) for _ in range(n * n)]
    program = f"""teams←{bpl_strings(teams)}
goals←{n} {n}ρ{bpl_numbers(goals)}
goals←goals×~(ι{n})=⊗ι{n}
points←+/(3×goals>⍉goals)+goals=⍉goals
⎕←points
order←⍒points
⎕←order⊃¨⊂teams
⎕←(order⊃¨⊂teams),¨(⊂": "),¨⍕¨order⊃¨⊂points
"""
    return {"files": {"league.bpl": program}, "argv": ["league.bpl"]}


def module_program(rng: random.Random) -> dict:
    """A program and a module of its own: `stats.bpl` defines summary functions and a private
    helper; `main.bpl` loads it with `•load` and uses what it exports on seeded data."""
    values = [rng.randint(1, 90) for _ in range(rng.randint(4, 12))]
    module = """⍝ Summary statistics
_square←×⍨
mean←+/÷≢
variance←{(+/_square ω-mean ω)÷≢ω}
spread←{(⌈/ω)-⌊/ω}
describe←{["mean":(mean ω) "variance":(variance ω) "spread":(spread ω)]}
"""
    main = f"""[mean: spread: describe:]←•load "stats.bpl"
data←{bpl_numbers(values)}
⎕←mean data
⎕←spread data
⎕←describe data
s←•load "stats.bpl"
⎕←s.variance data
"""
    return {"files": {"stats.bpl": module, "main.bpl": main}, "argv": ["main.bpl"]}


def dash_program(rng: random.Random) -> dict:
    """A program given on standard input with `bpl -` and arguments after it, which it reads
    with `•host "args"`."""
    args = [str(rng.randint(1, 99)) for _ in range(rng.randint(1, 4))]
    program = """args←•host "args"
⎕←≢args
n←⍎¨args
⎕←+/n
⎕←⌽n
"""
    return {"files": {}, "argv": ["-", *args], "stdin": program}


TEMPLATES = [sales_report, grade_book, word_count, run_lengths, ledger, temperatures, primes, matrices, histogram,
             cipher, fibonacci, collatz, validator, inventory, rationals, complex_roots, newton, text_tools, csv_report,
             json_transform, base_conversion, moving_average, tournament, module_program, dash_program]


def program_cases(rng: random.Random, count: int) -> list[dict]:
    """`count` program cases, cycling through TEMPLATES in a seeded order, each with its own data."""
    order = list(TEMPLATES)
    rng.shuffle(order)
    found = []
    for index in range(count):
        template = order[index % len(order)]
        built = template(rng)
        found.append({"kind": "program", "source": template.__name__, "argv": built["argv"], "files": built["files"],
                      "stdin": built.get("stdin"), "family": template.__name__})
    return found


DISPLAY_VALUES = [
    lambda rng: f"{rng.randint(2, 6)} {rng.randint(2, 7)}ρι{rng.randint(5, 40)}",
    lambda rng: f"{rng.randint(2, 5)} {rng.randint(2, 5)}ρ{rng.choice(['0.5', '1.25', '3.75', '¯2.5'])}×ι{rng.randint(4, 20)}",
    lambda rng: f'{rng.randint(2, 4)} {rng.randint(2, 6)}ρ"{"".join(rng.choice("abcdefgh") for _ in range(rng.randint(3, 9)))}"',
    lambda rng: f"(ι{rng.randint(2, 4)}) ({rng.randint(2, 3)} {rng.randint(2, 3)}ρι9) \"{rng.choice(PLACES)}\"",
    lambda rng: f"{rng.randint(30, 300)}ρ{rng.randint(1, 9)}×ι{rng.randint(3, 12)}",
    lambda rng: f"{rng.randint(12, 40)} {rng.randint(12, 40)}ρι{rng.randint(50, 900)}",
    lambda rng: f"÷1+ι{rng.randint(3, 12)}",
    lambda rng: f"{bpl_strings(rng.sample(ITEMS, 3))}:{bpl_numbers([rng.randint(1, 50) for _ in range(3)])}",
    lambda rng: f"⊂⊂{bpl_numbers([rng.randint(1, 9) for _ in range(rng.randint(2, 4))])}",
    lambda rng: f"{rng.randint(2, 3)} {rng.randint(2, 3)} {rng.randint(2, 4)}ρι{rng.randint(8, 30)}ₓ",
    lambda rng: f"*{rng.randint(10, 60)}×ι{rng.randint(2, 6)}",
    lambda rng: f"(ι{rng.randint(1, 3)}) ⍬ (0 {rng.randint(1, 3)}ρ0)",
]
DISPLAY_FUNCTIONS = ["+/÷≢", "{α+2×ω}", "(+/÷≢)⍤1", "{ω≤1?1;ω×∇ω-1}", "⌽∘⍉", "+.×", "-⍨", "2↣×", "{⍶¨ω}", "≢⍤⊢⌸",
                     "{[a b]←ω ◇ a+b}", "×⍨@{ω>3}"]


def display_cases(rng: random.Random, count: int) -> list[dict]:
    """`count` display cases on values and functions built here: boxes, the item limit and
    edges, the line width, float precision, diagrams, trees, notation and `⍕` with a spec."""
    found = []
    for _ in range(count):
        if rng.random() < 0.25:
            function = rng.choice(DISPLAY_FUNCTIONS)
            head = rng.choice(['•prefs ["trees":$t]', '•prefs ["trees":$f]', '•prefs ["notation":"traditional"]',
                               '•prefs ["notation":"simplified"]', '•prefs ["box":$t]'])
            program = f"{head}\nf←{function}\nf\n"
        else:
            value = rng.choice(DISPLAY_VALUES)(rng)
            head = rng.choice(['•prefs ["box":$t]', f'•prefs ["limit":{rng.choice([10, 30, 100])} "edges":{rng.randint(1, 4)}]',
                               f'•prefs ["width":{rng.choice([16, 24, 40, 72])}]', f'•prefs ["prec":{rng.randint(2, 16)}]',
                               "", "", f"{rng.choice(['2', '¯3', '8 2', '⍬', '0 1', '6 0'])}⍕"])
            if head.endswith("⍕"):
                program = f"{head}{value}\n"
            elif head:
                program = f"{head}\n{value}\n⎕←{value}\n"
            else:
                program = f"]display {value}\n"
        found.append({"kind": "display", "source": "display", "argv": ["show.bpl"], "files": {"show.bpl": program},
                      "stdin": None, "form": "built"})
    return found
