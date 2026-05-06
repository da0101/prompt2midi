# Git Flow Conventions

Last updated: 2026-05-06

## Branch Roles

- `develop` is the integration branch and default working base.
- `main` is release-only and should match the latest tagged release candidate or release.
- Feature branches start from `develop` and merge back into `develop`.
- Release promotion is `develop` -> `main`, followed by an annotated version tag.

## Feature Work

```bash
git switch develop
git pull --ff-only
git switch -c feature/<stream-or-task-slug>
```

Open PRs from `feature/<slug>` into `develop`.

## Release Work

When `develop` is ready to ship:

```bash
git switch main
git pull --ff-only
git merge --no-ff develop
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main vX.Y.Z
```

Use `main` only for release merges, release fixes, and tags.
