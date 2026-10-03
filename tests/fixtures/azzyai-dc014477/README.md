# AzzyAI source fixture

`USER_AI/` is the extracted subtree from the official GitHub archive for the
commit selected by `scripts/azzyai.py`. The direct tests copy it into a
temporary directory before exercising the production verifier. It is never
executed and is not an installation fallback.
