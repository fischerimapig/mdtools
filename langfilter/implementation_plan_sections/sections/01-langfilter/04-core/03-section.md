
```
for each line:
  NORMAL:
    code fence? → IN_CODE_FENCE, emit
    lang open?  → IN_LANG_BLOCK
      match lang? → emit (keep with markers)
      else        → skip (remove)
    otherwise   → emit

  IN_CODE_FENCE:
    always emit
    closing fence? → NORMAL

  IN_LANG_BLOCK:
    lang close? → NORMAL
      match lang? → emit closing :::
      else        → skip
    otherwise:
      match lang? → emit content
      else        → skip
```
