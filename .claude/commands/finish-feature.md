---
description: Commit, push, open a PR into main, merge it (rebase if main hasn't moved since the branch diverged, otherwise a merge commit), then clean up the feature branch locally and on the remote.
allowed-tools: Bash(git:*), Bash(gh:*)
---

You are shipping the current feature branch for the Spendly expense
tracker: commit outstanding work, open a PR, merge it, and clean up.

## Step 1 — Confirm you're on a feature branch

Run `git branch --show-current`. If the current branch is `main`, stop
immediately and tell the user this command only runs from a feature
branch.

## Step 2 — Commit all changes

Run `git status` to see staged/unstaged/untracked changes. If there is
nothing to commit, skip to Step 3.

Review `git status` output before staging — do not blindly `git add -A`.
Check for anything that looks like a secret or generated artifact that
shouldn't be committed, and warn the user if you see one.

Look at `git diff` / `git diff --staged` and `git log --oneline -5` to
understand what changed and match the repo's existing commit style.
Write a **Conventional Commits** message (`type(scope): summary`, e.g.
`feat(expenses): add expense form with validation`) — one concise summary
line describing what changed and why, matching the style VS Code's Source
Control "Generate Commit Message" produces (terse, no filler, present
tense). Use `fix`/`feat`/`test`/`refactor`/`chore`/`docs` as appropriate;
if the diff spans multiple unrelated concerns, pick the dominant one for
the summary line and list the rest as bullet points in the body.

Commit with:
```
git add <specific files>
git commit -m "$(cat <<'EOF'
<type>(<scope>): <summary>

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

## Step 3 — Push to the feature branch

```
git push -u origin <current-branch>
```

## Step 4 — Create the pull request

Gather the full scope of the branch, not just the latest commit:
- `git log main..HEAD --oneline` — every commit on the branch
- `git diff main...HEAD --stat` — every file touched

Write a PR title (under 70 characters) and a body with a `## Summary`
(bullet points covering everything implemented across all commits on the
branch) and a `## Test plan` (checklist) section.

```
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Step 5 — Determine merge strategy and merge

```
git fetch origin main
MERGE_BASE=$(git merge-base HEAD origin/main)
MAIN_HEAD=$(git rev-parse origin/main)
```

- If `$MERGE_BASE` equals `$MAIN_HEAD`, `main` hasn't advanced since this
  branch diverged from it — merge with rebase:
  ```
  gh pr merge --rebase --delete-branch
  ```
- Otherwise `main` has moved on since the branch diverged — merge with a
  real merge commit:
  ```
  gh pr merge --merge --delete-branch
  ```

`--delete-branch` deletes the remote feature branch as part of the merge.

Before merging, confirm the PR is actually mergeable
(`gh pr view --json mergeable,mergeStateStatus`). If it reports conflicts
or failing required checks, stop and report — do not force-merge.

## Step 6 — Clean up locally

```
git checkout main
git pull origin main
git branch -D <feature-branch>
```

Use `-D` (force), not `-d`: a rebase-merge creates new commit SHAs on
`main`, so the local branch's original commits won't be recognized as
"already merged" by git's safe-delete check even though the PR is
confirmed merged. Only run this after confirming the PR's state is
`MERGED` (`gh pr view <number> --json state`).

## Rules

- Never force-push
- Never merge locally and push straight to `main` — always merge through
  `gh pr merge`
- If `gh pr merge` reports the PR isn't mergeable, stop and report — do
  not force-merge or bypass checks
- Confirm the PR's state is `MERGED` before deleting the local branch
- Report the final state to the user: PR URL, merge strategy used, and
  confirmation that both the remote and local feature branches are gone
