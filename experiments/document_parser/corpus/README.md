# Fixed M2 compatibility and intentional-change corpus

`m2.json` is language-independent evidence for baseline
`b11368128d4e2a476f2204af40bdfdc947f1cc88`. The prototype worktree starts at
`17723261c3a9a47f69b763d4898c1db0d290c0fd`, whose tree is identical to that
baseline. The test adapter is confined to `tests/legacy_adapter.py`; neither the
prototype implementation nor its fallback may import it.

There are 19 compatibility cases (C), three independently expected Issue #51
changes (I), and two unapproved intentional-change observations (I). C includes
all three cancellation manuscripts and normal, multilingual, natural-only,
invalid, and broken-model model-contract manuscripts. The remaining C inputs
cover ordinary IDs, body-only text, malformed headers, unclosed Divs, literal
fences/comments/code spans/HTML attributes, Unicode content and LF/CRLF/CR.

Every case declares the exact comparison fields. They are not reduced to an
intersection of whichever fields the implementations happen to return. All
candidate IDs and order, original UTF-8 half-open spans, raw bodies, languages,
mdspec spans and direct/nested membership are compared. For normal retained
requirements, bodies come from the old public parser; generic structure supplies
fence boundaries and header validity. For rejected malformed/missing-ID
candidates, the baseline scanner provides observations without reinterpreting
rejection as absence. Public retained IDs, diagnostics, rejected spans and
completeness are recorded separately. They are historical evidence, not a new
semantic-validation contract.

Expected C candidate projections were frozen from baseline observations; expected
ID lists were independently specified. The three Issue #51 expectations require
REQ-A and its exact original byte span independently of either parser. Link,
image and reference titles contain `<!--`, and all three old observations lose
the following requirement. The genuine block comment, code span, HTML quoted
attribute and fence controls remain C. Unclosed paragraph comments and Div-tail
comments remain I observations with explicit unsupported reasons and no approved
new expectation. No production behavior change is authorized by this corpus.

All semantic checks in the new summary must remain `not-run`. JSON/model
validation, expression evaluation and reference resolution are deliberately not
asserted compatible. Structural partial results must preserve candidates; a
prototype `failed` result is never accepted as a successful zero-case parse.
