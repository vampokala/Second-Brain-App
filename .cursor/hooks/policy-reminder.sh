#!/usr/bin/env bash
# beforeSubmitPrompt: detect anti-quality prompts ("skip tests", "ignore lint", "disable coverage")
# and inject a policy reminder. Does NOT block - just makes the policy visible.
set -uo pipefail

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // .user_prompt // empty')

if [ -z "$PROMPT" ]; then
  echo '{}'
  exit 0
fi

PATTERNS='(skip|disable|bypass|ignore|remove).*(tests?|coverage|lint|pre-commit|sonarqube|quality|--no-verify|@ts-ignore|noqa|suppresswarnings)'

if echo "$PROMPT" | grep -qiE "$PATTERNS"; then
  REMINDER="Policy reminder: requests to skip quality gates require an exemption ticket per docs/exception-process.md.
- Tests are required on every change (see .cursor/rules/tests-required.mdc).
- Coverage threshold: >= 80% line / >= 70% branch on new code.
- --no-verify, @ts-ignore, # noqa, @SuppressWarnings must reference a JIRA ticket and expire in 30 days.

If the user has explicit authorization, proceed and note it in the PR. Otherwise propose adding tests/refactoring instead."
  jq -n --arg ctx "$REMINDER" '{additional_context: $ctx}'
  exit 0
fi

echo '{}'
exit 0
