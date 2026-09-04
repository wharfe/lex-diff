"""Shared Claude API helpers for the annotate / law_summary / explainer scripts.

The three scripts had a copy of response_text() each, which is how they drifted
apart in the first place. Keeping one copy also means the "never persist a
half-written answer" guard below can only be forgotten in one place.
"""

import json


def response_text(response) -> str:
    """The first text block of a response, or an error.

    Two things are checked here rather than at each call site:

    - Current models emit thinking blocks before the text, so content[0] is not
      necessarily the answer.
    - stop_reason == "max_tokens" means the answer was cut off mid-sentence.
      Callers parse this as JSON and, on failure, used to store the raw
      fragment as if it were prose — which shipped literal JSON to readers
      (11 articles across 8 law pages, found in Gate3). A truncated answer is
      not a cheaper answer; it is a failure, so it raises.
    """
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ValueError(
            "response hit max_tokens and is truncated — raise max_tokens "
            "rather than saving a partial answer"
        )
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    raise ValueError("no text block in response")


def strip_code_fence(text: str) -> str:
    """Remove a ```json ... ``` wrapper if the model added one."""
    if not text.startswith("```"):
        return text
    body = text[3:]
    # ```json{...}``` with no newline used to raise IndexError on the split.
    if "\n" in body:
        body = body.split("\n", 1)[1]
    else:
        body = body.lstrip("json").lstrip()
    return body.rsplit("```", 1)[0].strip()


def complete_json(client, model: str, prompt: str, max_tokens: int) -> dict:
    """Ask for JSON and return it parsed. Raises rather than returning junk."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(strip_code_fence(response_text(response)))
