# The target domain

The model you deliver is a general-purpose decision model for short texts. Each request gives it one piece of text
(the state) and one question with a fixed set of answers, and the model has to pick the right answer and give
probabilities that mean what they say. Nobody writes free text back; the answer is always one of the listed options.

## Kinds of decisions

About three quarters of the questions come from these six kinds, in roughly equal shares:

- **General knowledge.** A multiple-choice question from an academic or professional subject (history, law,
  medicine, biology, economics and so on) with four options. The state names the subject.
- **Science.** A multiple-choice science question with four options, sometimes with a supporting passage.
- **Emotion.** A short first-person sentence; which emotion does the writer express: sadness, joy, love, anger, fear
  or surprise.
- **Offensive posts.** A social-media post (user names masked); is it offensive, yes or no.
- **Answer present.** A question and a sentence; does the sentence contain the answer to the question, yes or no.
- **Same meaning.** Two sentences that share most of their words; do they mean the same thing, yes or no.

The other quarter applies written rules to a case:

- **Business policies.** A policy and a case described in a few sentences. Either whether a refund is authorized
  (yes or no, which depends on who signed and who may sign), or how late a report is against a deadline with a grace
  period (on time, late but accepted, refused).
- **Compound rules.** An approve-or-deny rule built from named conditions joined with and, or, not, if-then-else and
  unless, nested two or three levels, and a case that lists the values, some of them irrelevant. Conditions compare
  numbers, names and yes/no flags, and some count the days between two dates. The answer is accept or reject. The rule
  shapes and the wording of these rules are not ones Kev trained on.

## Question types

All three of Kev's question types occur: `choice` (pick one option), `noul` (true or false) and `score` (an ordered
level). States are short, from one sentence to a passage of a few hundred words.

`/opt/task/public-20.jsonl` has 20 labelled examples drawn from this domain, in Kev's request format.
