#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/app.git"
DATE_POSTFIX=`date '+%Y%m%d-%H%M%S'`
OUTDIR="$HOME/devops/tmp/sec_$DATE_POSTFIX"
mkdir -p "$OUTDIR"

while read -r oldrev newrev refname; do
  [ "$newrev" = "0000000000000000000000000000000000000000" ] && continue

  for commit in $(git --git-dir="$REPO" rev-list "$oldrev..$newrev"); do
    sha=$(git --git-dir="$REPO" rev-parse --short "$commit")
    author=$(git --git-dir="$REPO" show -s --format='%an <%ae>' "$commit")
    subject=$(git --git-dir="$REPO" show -s --format='%s' "$commit")
    {
      echo "# Commit $sha"
      echo
      echo "**Author:** $author"
      echo "**Subject:** $subject"
      echo
      echo "## Files changed"
      git --git-dir="$REPO" diff-tree --no-commit-id --name-status -r "$commit"
      echo
      echo "## Diff"
      git --git-dir="$REPO" show --stat --patch --format=medium "$commit"
    } > "$OUTDIR/$sha.md"
  done
done

cd $OUTDIR
cline "
You are a senior security engineer and code reviewer. Perform a thorough security and best-practices audit of the following git push request.

Input:
Check the content of commit.log

Output:
Create a file security.log

Task:
Conduct a structured review with explicit reasoning. Do NOT summarize everything in one paragraph.

1. High-level summary
   - What the change does
   - Risk level (Low / Medium / High)
   - Scope of impact

2. Security review (MANDATORY – even if no issues)
   For each category below, explicitly state:
   - Status: OK / Issue / Needs confirmation
   - Explanation

   Categories:
   - Secrets exposure (keys, tokens, credentials)
   - Input validation & injection risks (SQL, command, XSS, etc.)
   - Authentication / authorization impact
   - Network exposure (ports, bindings, external access)
   - Data handling (PII, logging sensitive data)
   - Dependency risks (new libraries, versions)

3. Best-practices review
   - Code duplication
   - Error handling
   - Logging quality
   - Test coverage impact
   - Maintainability / readability
   - Configuration management

4. Findings (only if applicable)
   For each issue:
   - Severity: Low / Medium / High
   - Description
   - Location (file / component)
   - Recommendation

5. Positive signals
   - Call out things that are well implemented (consistency, reuse, safety patterns, etc.)

6. Final recommendation
   - Short justification

Rules:
- Be explicit and structured — no single-paragraph answers
- Do NOT hallucinate issues
- If unsure, say "Needs confirmation"
- Prefer precise technical language over vague statements

Output format (strict):

## Summary
...

## Security Review
- Secrets exposure: ...
- Input validation: ...
- Authentication / Authorization: ...
- Network exposure: ...
- Data handling: ...
- Dependencies: ...

## Best Practices
...

## Findings
...

## Positive Signals
...

## Final Recommendation

Action to take: none -> urgent
"
