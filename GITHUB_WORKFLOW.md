# Flash-iOS GitHub Access & Commit Workflow

## How to use this file in a new ChatGPT thread

Upload this file at the start of a new Flash-iOS development thread and tell the assistant:

> Use this file as the GitHub workflow and access policy for this project. Follow it before making or claiming any GitHub changes.

This file is intended to give a new thread enough context to use the GitHub connector safely and consistently without repeating the setup process.

---

## Repository and branch layout

Primary writable fork:

- Repository: `KingdomDesignsConsulting/Flash-iOS`
- Active development branch: `flash-moe-production`
- `origin`: `KingdomDesignsConsulting/Flash-iOS`
- `upstream`: `Anemll/Flash-iOS`

Normal workflow:

```text
source edit / experiment
        ↓
compile locally
        ↓
runtime validation locally
        ↓
evaluate results
        ↓
update docs if meaningful
        ↓
focused Git commit
        ↓
push/update flash-moe-production
```

Do not modify `main` unless explicitly requested.

Do not merge `flash-moe-production` into `main` unless explicitly requested.

Do not rewrite Git history, force-push, amend old commits, or rebase shared history unless explicitly authorized.

---

## GitHub connector setup

The ChatGPT GitHub plugin must be installed as an actual GitHub App installation on:

`KingdomDesignsConsulting`

The working installation currently has repository access set to:

`All repositories`

The ChatGPT-side plugin permission should allow write actions. In the successful setup, the plugin was configured with full action access.

### Important distinction

A GitHub plugin can appear connected in ChatGPT and advertise `Write` capability while still lacking an actual GitHub App repository installation.

That happened during setup.

The failure state looked like this:

- ChatGPT showed GitHub as connected.
- The plugin UI showed write capability.
- GitHub identity calls worked.
- Public repository reads worked.
- `list_installations` returned no installations.
- Write operations such as `create_blob` and `create_branch` failed with:

```text
403 Resource not accessible by integration
```

The fix was:

1. Uninstall/disconnect the GitHub plugin.
2. Reinstall/reconnect it.
3. During GitHub authorization, grant access to the `KingdomDesignsConsulting` account.
4. Grant repository access. `All repositories` was selected.
5. Recheck the GitHub App installation from ChatGPT.
6. Verify repository push permission.
7. Run a harmless write probe.

After reinstalling, ChatGPT successfully saw a real installation.

At the time this file was written:

- GitHub account: `KingdomDesignsConsulting`
- Installation ID: `168121567`
- Repository selection: `all`
- `KingdomDesignsConsulting/Flash-iOS` was visible through that installation.
- Reported repository permissions included:
  - `admin: true`
  - `maintain: true`
  - `pull: true`
  - `push: true`
  - `triage: true`

---

## Recommended verification sequence in a new thread

Before making the first GitHub write in a new thread, verify the connector rather than assuming access still works.

### 1. Verify the GitHub App installation

Use the GitHub connector to list installations.

Expected result:

- An installation for `KingdomDesignsConsulting`
- Repository access that includes `KingdomDesignsConsulting/Flash-iOS`

If the connector reports zero installations, do not attempt to commit or claim write access.

### 2. Verify repository visibility and permissions

Confirm that the installed account can see:

`KingdomDesignsConsulting/Flash-iOS`

and that the returned permissions include:

`push: true`

### 3. If write access is uncertain, use a harmless blob probe

A safe test is GitHub's low-level `create_blob` operation.

Creating a blob stores an unreferenced Git object but does not:

- modify a branch,
- create a commit,
- modify the working development history,
- change `flash-moe-production`,
- change `main`.

The successful write-access probe during setup created this blob:

```text
876ab9fa8866dc77a1188c169ddc5298af5a5b60
```

That SHA is only historical proof that writes worked at that moment. A future thread should perform a new probe if access is in doubt.

If `create_blob` returns:

```text
403 Resource not accessible by integration
```

then the connector does not currently have usable repository write authorization.

---

## Preferred Git commit method

For meaningful code or documentation work, prefer focused commits.

Suggested commit prefixes:

```text
experiment:
bench:
perf:
fix:
docs:
```

Examples:

```text
perf: split routed gate-up kernels by quantization width
bench: record N128 bitsplit gate-up results
fix: prefer project-local grouped shader source
docs: update current N128 optimization status
```

### Atomic multi-file commits

When several files belong to one logical change, prefer the low-level Git object flow when available:

```text
create_blob
    ↓
create_tree
    ↓
create_commit
    ↓
update_ref
```

This allows multiple files to be committed atomically instead of using one GitHub Contents API commit per file.

For branch updates:

- use fast-forward updates,
- use `force=false`,
- use the expected current branch SHA when supported,
- re-fetch the branch head before retrying if the ref changed.

Do not silently force-update a branch.

---

## Branch policy

Normal target:

`flash-moe-production`

Do not commit directly to `main` unless explicitly instructed.

For experimental work that should not touch the active branch, create an isolated temporary or experiment branch first.

Examples:

```text
experiment/<name>
bench/<name>
connector-write-test
```

The assistant should state which branch it is modifying before making a write if there is any ambiguity.

---

## Commit discipline

A Git commit should represent one coherent change whenever practical.

Good examples:

- one accepted optimization,
- one rejected experiment plus its benchmark documentation,
- one correctness fix,
- one documentation synchronization,
- one benchmark target addition.

Avoid mixing unrelated work into a single commit.

Meaningful rejected experiments may still deserve commits if preserving the implementation and evidence is useful.

---

## What must be verified before claiming success

The assistant must distinguish these stages clearly:

### Source inspection

The assistant inspected code or documentation.

This does not mean anything was written.

### Source write

A file was actually modified through the relevant connector or repository write operation.

Do not say a write succeeded unless the tool confirms it.

### Compile validation

The code compiled successfully.

For Flash-iOS, this normally requires the user to run the build on the Mac unless a suitable local execution environment is explicitly available.

Do not infer successful compilation from source inspection.

### Runtime validation

The resulting binary was actually run against the intended test.

Do not claim runtime correctness or performance without runtime output.

### Git commit

GitHub confirmed creation of a commit.

Do not claim a commit exists from an intended commit message or an attempted tool call.

### Branch update / push

The target branch actually points to the new commit.

After a low-level commit flow, verify the branch head if practical.

---

## Current documentation status

The canonical active project status document is:

`docs/CURRENT_STATUS.md`

`docs/DEVELOPMENT.md` links to it and contains development workflow information.

The documentation synchronization performed before this GitHub connector setup was pushed to:

```text
854627976da7c53ee7088fe4e012b84efa1766d6
```

Short commit:

```text
8546279
```

That commit contained the synchronized documentation set.

A new thread should read `docs/CURRENT_STATUS.md` before making architecture or optimization assumptions.

Historical documents may intentionally preserve older states. Do not rewrite dated history merely because the current production configuration has changed.

---

## Flash-iOS production safety rules

Production serving port:

```text
11436
```

Do not disturb it during isolated benchmark or candidate testing.

Isolated serving tests use:

```text
11437
```

The production executable should not be silently replaced by benchmark-only candidates.

Experimental Makefile targets should normally build separate binaries under the testing/apps area.

---

## Current Git workflow expectations

For substantial changes:

1. Inspect the current repository source.
2. Make the smallest coherent source change.
3. Have the user compile if local Mac compilation is required.
4. Have the user run the appropriate correctness/performance test.
5. Evaluate the results.
6. If accepted or meaningfully rejected, update the relevant documentation.
7. Create a focused commit on `flash-moe-production`.
8. Verify the resulting commit SHA and branch head.
9. Report exactly what changed and what remains unvalidated.

Do not claim that a GitHub commit implies successful compile or runtime validation.

---

## Google Drive vs GitHub source

The Flash-iOS project historically used a Google Drive mirror for active source inspection and editing.

A Git checkout and GitHub workflow are now established.

When both Drive and GitHub copies exist, do not assume they are identical.

Before making a Git commit:

- determine which source copy is authoritative for the current task,
- inspect the latest GitHub branch state,
- avoid overwriting newer Git changes with an older Drive copy,
- synchronize deliberately when necessary.

`docs/CURRENT_STATUS.md` should be treated as the canonical high-level current-state summary.

---

## Previous access failure and final resolution

### Failure

The plugin appeared installed and connected, but ChatGPT's GitHub connector reported:

```text
installations: []
```

Write attempts such as:

```text
create_blob
create_branch
```

returned:

```text
403 Resource not accessible by integration
```

### Resolution

The GitHub plugin was uninstalled and reinstalled.

During reinstall, GitHub explicitly asked for repository access and access to all repositories was granted.

Afterward, the connector reported a real GitHub App installation for:

```text
KingdomDesignsConsulting
```

and `KingdomDesignsConsulting/Flash-iOS` showed:

```text
push: true
```

A harmless `create_blob` probe then succeeded.

That is the state that should be reproduced if GitHub write access ever stops working again.

---

## Troubleshooting checklist

If GitHub writes stop working:

1. Confirm the ChatGPT GitHub plugin is connected.
2. Check that it is allowed to perform write actions in ChatGPT.
3. Run `list_installations`.
4. Confirm a `KingdomDesignsConsulting` installation exists.
5. Confirm `Flash-iOS` is accessible through that installation.
6. Confirm the repository reports `push: true`.
7. Try a harmless `create_blob` write.
8. If writes return `403 Resource not accessible by integration` and installations are empty:
   - disconnect/uninstall the GitHub plugin,
   - reinstall it,
   - authorize `KingdomDesignsConsulting`,
   - grant repository access,
   - reconnect and re-test.
9. Do not work around a broken connector by pretending a write succeeded.
10. If necessary, the user can still use a local Git/Work workflow to commit and push.

---

## One-paragraph context for a new assistant

This project uses `KingdomDesignsConsulting/Flash-iOS` as the writable GitHub fork, with active development on `flash-moe-production` and `Anemll/Flash-iOS` as upstream. ChatGPT's GitHub plugin is installed as a real GitHub App installation on `KingdomDesignsConsulting`, currently with access to all repositories and confirmed push permission to Flash-iOS. Before writing, verify the installation and repository permissions; if uncertain, use a harmless `create_blob` probe. Prefer focused commits, atomic low-level Git object commits for multi-file changes when practical, fast-forward branch updates, no force pushes or history rewrites without explicit authorization, and never claim compile/runtime validation merely because a source write or Git commit succeeded. `docs/CURRENT_STATUS.md` is the canonical current-state document, production port 11436 must not be disturbed, and isolated serving tests use 11437.
