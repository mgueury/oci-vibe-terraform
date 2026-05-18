#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/app.git"
DATE_POSTFIX=`date '+%Y%m%d-%H%M%S'`
OUTDIR="$HOME/devops/tmp/doc_$DATE_POSTFIX"
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
    } > "$OUTDIR/$sha.log"
  done
done

cd $OUTDIR
cline "
You are a technical writer. Generate clear, accurate documentation from the following git push request.

Input:
Check the content of $sha.log

Output:
Create a file doc.md with the output result

Task:
1. Read the request and infer the purpose of the change.
2. Write documentation that explains:
   - what changed
   - why it changed
   - how it works
   - any setup, config, or migration steps
   - any user-facing impact
   - risks, limitations, or edge cases
3. Keep the documentation concise, structured, and easy to scan.
4. Use headings, bullets, and examples where helpful.
5. Do not invent details that are not supported by the input. Mark unclear points as "Needs confirmation" rather than guessing.
6. If the change affects an API, CLI, UI, or operational behavior, include a short "Before / After" section.
7. End with a short checklist of follow-up items for reviewers or maintainers.

Output format:
- Title
- Summary
- Details
- Usage / Migration
- Risks / Notes
- Follow-up checklist
"
cd -
cp $OUTDIR/doc.md .