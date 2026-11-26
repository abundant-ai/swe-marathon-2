# The target domains

The model reads one short text (the state) and one or more questions, each with a fixed set of answers, and picks an
answer for every question. It never writes free text. Questions are `choice` (pick one option), `noul` (true or false)
or `score` (an ordered level).

## Kinds of questions

**Classifying short texts**
- Topic of a news story or of an encyclopedia entry.
- Intent of a bank customer's message, out of many fine-grained intents.
- What kind of answer a question asks for (a person, a place, a number, a description and so on).
- Sentiment or star rating of a product, restaurant or film review, sometimes asked as a yes/no question.
- Emotion a short first-person sentence expresses: sadness, joy, love, anger, fear or surprise.
- Whether a social-media post is offensive.

**Reading and comparing sentences**
- A yes/no question about a passage.
- Whether one sentence follows from another, contradicts it, or neither.
- Whether a sentence contains the answer to a question.
- Whether two sentences that share most of their words mean the same thing.

**Knowledge**
- Multiple-choice questions from academic and professional subjects, and science questions, some with a supporting
  passage, each with four options.

**Applying written rules**
- A business policy and a case: return windows, spending limits, age eligibility, quantity limits, refund
  authorization, or how late a report is against a deadline with a grace period.
- An approve-or-deny rule built from named conditions joined with and, or, not, if-then-else and unless, nested
  several levels, with a case that lists the values, some of them irrelevant. Conditions compare numbers, names and
  yes/no flags, and some count the days between two dates.

States run from one sentence to a passage of a few hundred words. `/opt/task/public-20.jsonl` has 20 labelled
examples from these domains in Kev's request format.
