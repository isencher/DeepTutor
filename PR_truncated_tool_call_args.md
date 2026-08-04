# fix(chat): guard against truncated tool-call arguments

## Problem

When a chat-loop round hits the output token budget **while the model is still
streaming a tool call's arguments** (`finish_reason: "length"`), the arguments
JSON is cut off mid-string. The loop dispatched that garbled call anyway:

1. `agent_loop._call_llm` captured `finish_reason` but nothing ever consumed
   it — a truncated round looked exactly like a normal tool round.
2. `tool_dispatch._prepare_tool_args` parsed the truncated JSON via
   `parse_json_response(..., fallback={})`. When repair was unavailable or
   impossible, the call silently degraded to **empty arguments**.
3. The tool then executed with every argument missing and failed with a
   confusing downstream error. Real-world example: `write_note` reported
   `Unknown mode ''` — the `mode` the model sent never arrived.

Reproduction: ask the chat agent to write a very large document into a
notebook in one `write_note` call (a multi-section markdown body in
`content`). The arguments payload exceeds the round's `max_tokens`
(default 8000), the JSON is truncated, and the tool errors with
`Unknown mode ''` even though the model passed `mode="append"`.

## Fix

Two layered guards:

- **`deeptutor/agents/chat/agent_loop.py`** — detect truncation
  (`finish_reason` in `{"length", "max_tokens", "model_context_window_exceeded"}`,
  case-insensitive) on a round that carries tool calls, and instead of
  dispatching the garbled call, nudge the model once to retry the same tool
  with much smaller arguments (shorten/omit large text fields, split the
  payload across calls). The nudge fires at most once per turn; if the model
  truncates again, the round falls through to dispatch so the second guard
  can answer it. User-facing warning + model-facing nudge are i18n'd
  (`prompts/{en,zh}/agentic_chat.yaml`).

- **`deeptutor/core/agentic/tool_dispatch.py`** — `_prepare_tool_args` now
  distinguishes "arguments empty / legitimately `{}`" from "non-empty payload
  that cannot be parsed into a JSON object at all" (using an explicit
  `fallback=None`). Unparseable calls are marked and short-circuited in
  `_run_one` with an explicit, model-actionable error result (explains the
  likely cause — oversized payload truncated by the token budget — and how to
  retry) instead of executing the tool with empty arguments. Non-dict JSON
  (double-encoded strings, arrays, scalars) is flagged the same way.

Why both layers: with `json-repair` installed, mildly truncated JSON is
salvaged into a partial dict and parsing "succeeds", so the parse guard alone
cannot catch truncation — the `finish_reason` check can. Conversely, the
parse guard catches unrecoverable payloads regardless of how they arose
(provider quirks, DSML edge cases, missing `json-repair`).

## Tests

- `tests/agents/chat/test_agent_loop.py`
  - `test_truncated_tool_call_nudges_once_then_recovers` — a `length`
    truncated tool round is not dispatched; the model is nudged and recovers.
  - `test_repeated_truncation_falls_through_to_dispatch_parse_guard` — the
    nudge fires once; a second truncated round is dispatched and answered by
    the parse guard; the tool never executes.
- `tests/core/agentic/test_tool_dispatch_events.py`
  - `test_unparseable_arguments_short_circuit_with_actionable_error` —
    unparseable arguments short-circuit with an actionable error result
    (passes with and without `json-repair` installed).
  - `test_empty_arguments_object_is_not_a_parse_failure` — `{}` / omitted
    arguments still execute (no false positives).
  - `test_non_dict_json_arguments_are_a_parse_failure` — double-encoded /
    non-object JSON is flagged instead of silently executed empty.

`pytest tests/core/agentic tests/agents` — 165 passed; the one failure
(`test_prompt_identity.py::test_shipped_yaml_carries_partner_templates`) is a
pre-existing Windows GBK-locale decoding issue that also fails on the base
commit and is unrelated to this change.

## Notes

- No behavior change for well-formed tool calls; the new code paths only
  trigger on truncation or unparseable argument payloads.
- The parse-guard result text and the nudge copy deliberately tell the model
  *how* to recover (smaller arguments / split the payload), so the loop
  self-heals within the turn instead of failing the user's request.
