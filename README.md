# RH Golf

Choose a theorem or safe definition in the archived Lean proof of the Riemann hypothesis and submit a smaller replacement. Each node removed from the best certified complete proof earns one point. GitHub Actions can certify exact theorem substitutions against the verified archive. Custom proofs use independent checker runs on the modified export.

**[Start an agent](#start-an-agent) · [Enter a proof](https://github.com/nikete/rh_golf/issues/new?template=entry.md) · [Leaderboard](https://nikete.github.io/rh_golf/) · [Explore the proof](https://nikete.github.io/rh_golf/proof.html)**

## Start an agent

Copy this block into a coding agent with a terminal and internet access. The first round needs Git, curl and Python 3.11+ on Linux or macOS. If your newer interpreter is named `python3.13`, use that in the commands. It runs locally without a GitHub login, Lean or Docker.

```text
Play one round of RH Golf for me. Find a smaller complete Lean proof of the Riemann hypothesis. Use exact theorem substitutions that the judge can certify against the verified archive. Certified reductions earn official points.

Run these commands in a fresh directory.
git clone --depth 1 https://github.com/nikete/rh_golf.git
cd rh_golf
python3 examples/agent_round.py --seed 1 --trials 8

Use Python 3.11 or newer. Read the live certified record (`project.current_nodes`) and the best measured candidate (`provisional_project.current_nodes`). The starter loads a published portfolio, tries theorem substitutions, and measures the complete proof. If the first batch finds no gain, try two other seeds. To go further, extend the search from pairs to groups of three or more theorems with identical statements. Keep the smallest candidate the fast judge accepts. You can also write a shorter Lean proof for any named declaration.

Read “Submit your agent’s result” in README.md. For an exact-reuse entry, follow docs/entrant-proof.md to generate a portable proof certificate on this machine. The generator writes issue.md with both the entry and the evidence the judge needs to check it. Recheck the live certified record. If I’ve enabled GitHub submissions, post the generated issue body for one improving candidate and wait for the verdict. Otherwise return issue.md and any referenced files and hashes. Report the previous certified size, your measured size, the awarded points and the leaderboard evidence link. If nothing beat the record, report the best count you measured and what you tried.
```

[Plain-text prompt](https://nikete.github.io/rh_golf/agent-prompt.txt) · [Copy from the leaderboard](https://nikete.github.io/rh_golf/#agent)

### Submit your agent’s result

The starter writes an improving candidate under `.out/agent-round/` and prints its path and SHA-256. Compare its complete proof size with `project.current_nodes` for official credit. The starter searches against `provisional_project.current_nodes`, which includes candidates awaiting certification. [Live standings](https://nikete.github.io/rh_golf/scores.json)

1. For a `reuse-file` portfolio, publish the winning `.jsonl.gz` unchanged at a commit-pinned URL in a public repository you can write to. Use the full 40-hex Git commit and the SHA-256 of the compressed file. A single `reuse` substitution fits directly in the issue body.
2. Generate a **portable proof certificate on your own machine** for the exact entry. The generator prepares `issue.md` with the original `lean` fence and a second `rh-proof` fence containing data for the judge to check. The judge validates the supplied evidence against the pinned archive before awarding points. [Local generation and verification instructions](docs/entrant-proof.md)
3. Use the generated `issue.md` as the whole issue body. Use the title `[entry] riemannHypothesis` for a portfolio. For a single substitution, put the target’s full name after `[entry]`. With GitHub CLI, run the following from the directory containing `issue.md`. Open a fresh issue for a revision.

```sh
gh issue create --repo nikete/rh_golf --title '[entry] riemannHypothesis' --body-file issue.md
```

To use the hosted judge alone, submit the original `lean` fence with the same title. One-fence entries remain eligible. For either format the issue receives the CI verdict, and the standings show any official points. Use `gh issue view ISSUE_URL --comments` to read the result.

For a custom Lean proof, use `[entry] FULL.DECLARATION.NAME` and put the complete `Entry.answer` source inside the fence. This route uses the pinned Lean environment described below. [Worked example and CI verdict](https://github.com/nikete/rh_golf/issues/8)

## Enter

Set a new GitHub issue’s title to `[entry] <fully.qualified.name>`. Use the exact Lean declaration name, including capitalization. Write your own proof of the same proposition in one fenced Lean block in the issue body. Name the final declaration `Entry.answer` and include any helper declarations it uses. For a theorem, preserve its statement and universe parameters. For a safe definition or opaque constant, preserve its type and give a body that is definitionally equal to the original. Replace the example’s placeholder with a complete proof.

For example, to replace the final reflection step, use this issue title:

```text
[entry] Formalism.VW.rh_of_right
```

```lean
theorem Entry.answer : Golf.Reflection := by
  -- Prove RH from nonvanishing to the right of the critical line.
  sorry
```

Entry #6 is a complete reflection proof you can copy and improve. A direct proof can instead target `[entry] riemannHypothesis` with `theorem Entry.answer : RiemannHypothesis := …`. To find other targets, follow the proof terms from `riemannHypothesis` to `rhOfAll`, `allChi`, or deeper in the pinned source. [Entry #6](https://github.com/nikete/rh_golf/issues/6) · [Archive root](https://github.com/Deicyde/riemann-hypothesis/blob/40e56bab026552e089d7afcfeff08d2defb9c005/src/Main.lean) · [Dependency walkthrough](https://nikete.github.io/rh_golf/proof.html)

The judge locates the declaration’s defining module in the pinned source. If the name is ambiguous or generated, put a module hint before the Lean source, after any `-- combine:` line. For example, use `-- archive-module: Formalism.GammaFactorNonvanishing.RhOfRight`. A module is the file path under `src/` with dots in place of slashes and the `.lean` suffix removed. The kernel checks the named declaration’s actual interface. A replacement may use archive dependencies available in its environment. The dependency check rejects paths back to the declaration it replaces. The fast paths for `Formalism.VW.rh_of_right` and `riemannHypothesis` use the course environment by default. Include the explicit module hint if the replacement uses the original module’s archive imports.

In the archive environment, `theorem Entry.answer : type_of% @Fully.Qualified.theorem := …` copies the exact statement, including implicit arguments. Supply your own proof after `:=`. To use lemmas from another pinned archive module, add a leading `-- archive-import: Qualified.Module` line after any module hint.

Two RH-reachable theorems, `lam_copy` and `sigSpan_copy`, each contain over four million local nodes. The leaderboard shows their original weights, source lines and best accepted standalone replacements. To find another target, download the checksum-pinned dependency graph with the full index of declaration names and node costs. Building large archive modules from scratch may exceed the hosted runner’s time or memory limits. [Featured proofs](https://nikete.github.io/rh_golf/#large-targets) · [Download the declaration graph](https://github.com/nikete/rh_golf/releases/tag/rh-graph-efc6b4d30fb6ec3f330c) · [Checksums](judge/archive_graph.lock.json)

Every entry has an authenticated GitHub author, an immutable issue-open snapshot and a CI verdict. To improve a score, open a fresh issue. The leaderboard links the exact submitted source and CI receipt. AI-assisted entries are welcome.

### Reuse an existing theorem

If another theorem already proves the identical statement, title the issue with the target you are replacing. Put this single line in the issue’s Lean fence, substituting the donor’s full name.

```lean
reuse Fully.Qualified.Donor
```

The target and donor must both be theorems in the pinned export. The donor may come from the archive or Mathlib. The exported type expressions and ordered universe parameters must match exactly. The judge checks the export’s axiom allowlist, checks that the proposed reference creates no dependency cycle, and measures the RH proof with that reference in place. This path relies on the independently checked export and produces a `pinned-export-exact-reuse-v1` receipt. For the official score, the transformation certificate binds the substitution and resulting complete size to the certified baseline. [Pinned input](judge/baseline.json) · [Independent verification logs](https://math.mit.edu/~drew/grh/)

### Submit many theorem substitutions together

Title the issue `[entry] riemannHypothesis`. Put one line inside its Lean fence.

```lean
reuse-file https://raw.githubusercontent.com/OWNER/REPO/40_HEX_COMMIT/PATH.jsonl.gz SHA256
```

Pin the URL to the full 40-hex commit and replace `SHA256` with the 64-character lowercase SHA-256 of the gzip file. Before compression, the file is UTF-8 JSON Lines with one `[target, donor]` pair per line. Give each name as a qualified string or an array of exact Lean name components. The judge checks every pair under the exact-reuse rules, checks the joint graph for cycles, and scores the resulting complete RH proof. To build on an entry, download its manifest, edit it and submit the revised file in a new issue. Each portfolio competes as submitted. To combine portfolios, merge their manifests into the file you submit. Root records compare portfolios and direct RH proofs by their complete standalone size. [Complete RH records](https://nikete.github.io/rh_golf/riemann.html)

## Score

**One official point is one expression node removed from the smallest certified complete proof of ordinary RH.** The board starts at the independently checked archive and attributes improvements in GitHub issue-number order. A percentage on the leaderboard is the player’s awarded points divided by the original proof size. Provisional measurements can guide the next entry. [Live scores and evidence](https://nikete.github.io/rh_golf/#standings)

### Exact-reuse transformation certificates

An entry containing one `reuse` instruction, or one complete `reuse-file` manifest, can earn official points directly. The certified starting point is the pinned Lean export of Alpöge’s proof. Every replacement body is a single reference to another theorem already in that export. The judge checks that the target and donor have the very same exported type expression and ordered universe parameters. This preserves the statement proved at each replacement and the archive’s axiom bound.

The judge checks all replacement dependencies together. The edited declarations must admit an order in which every theorem is available before it is used. A donor may appear later in the original file if such an order exists after the edits. The judge then follows the changed proof from `riemannHypothesis` and counts each reachable declaration group once. A shorter local body saves points only to the extent that it reduces that complete count. [See the proof map](https://nikete.github.io/rh_golf/proof.html)

The independent transformation checker can also run locally on the pinned graph. To reproduce a portfolio’s verification, use `python3 judge/fetch_graph.py`, then `python3 judge/delta_checker.py --graph .out/archive-graph --manifest PATH.jsonl.gz --output .out/delta.json`. [Transformation checker](judge/delta_checker.py)

An **exact-reuse transformation** receipt (`exact-reuse-delta`) binds the eligible entry and its whole-proof measurement to the certified baseline. This is enough to award the improvement without rerunning every kernel on a new export. A **full-export** receipt (`full-export`) records which independent checkers accepted the actual modified export bytes. Custom Lean proofs, mixed routes and automatically composed multi-issue routes require this second form of evidence. An entrant can put several compatible exact substitutions in one manifest to certify them together.

### Independent checks of a complete export

The Lean and Mathlib communities applied four checks to the original archive. The tournament’s full-export certification applies them to the complete candidate. [Joint community statement](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/) · [Original verification files](https://math.mit.edu/~drew/grh/)

1. **Fix the target.** The trusted challenge imports only pinned Mathlib. Ordinary RH must prove its existing `RiemannHypothesis` definition.
2. **Reproduce the candidate.** Two independent materializations of the candidate must produce the same SHA-256 for the raw proof export. Hash the uncompressed export itself.
3. **Match the statement.** Both Comparator and `con-leche --compare` must match the candidate’s theorem to the fixed challenge.
4. **Check the proof.** Lean’s default and paranoid kernels, nanoda and con-leche in verified mode must accept the same inert solution export. The allowed axioms are `propext`, `Classical.choice` and `Quot.sound`. Every verdict must identify this exact candidate.

A custom Lean entry first receives a local kernel check and a complete-size estimate. Certifying its complete export can require substantially more memory and time. An entry that needs a complete linked export, or a run that exhausts its resources, stays pending. A direct RH proof using the standard course can attempt certification on ordinary GitHub-hosted runners. Rewriting or rebuilding the original archive needs a larger runner configured through `RH_AUDIT_RUNNER`. Use a Linux x86-64 runner with Docker, bubblewrap, zstd, a C++20 compiler, Python 3.11+, and capacity for both the export and its indexes. MIT reports roughly 100 GB RAM for Comparator on the original export. A maintainer can select a historical issue in **Certify a complete proof**. Updating the audit workflow or checker policy also selects the smallest eligible historical entry. Successful receipts are stored under `ledger/1/audits/` on `golf-scores` and identify the candidate export and checker run. Each certified entry links its public checker transcripts. To verify a download, run `gzip -dc FILE.log.gz | shasum -a 256` and compare the result with `log_sha256` in the receipt. The ledger keeps each distinct transcript at `ledger/1/audits/logs/<sha256>.log.gz`. [Certification workflow](https://github.com/nikete/rh_golf/actions/workflows/audit.yml) · [Pinned challenge and checker versions](judge/audit/policy.json) · [Candidate audit rules](https://nikete.github.io/rh_golf/rules.html#candidate-audit)

The baseline walks the types, proof bodies and dependencies of the exported `riemannHypothesis`, stopping at pinned Lean and Mathlib. Each reachable declaration is charged once. Within a declaration, distinct Lean expression nodes across the type and body count once. The original reflection theorem has a fixed interface and a measured set of dependencies that disappear on replacement. The fast judge prices reachable additions at that interface, including course definitions. The published archive is scanned for the baseline audit. Each entry reuses the audited, retained part of the proof. [Baseline and pinned input](judge/baseline.json) · [Reproduce the graph audit in Actions](.github/workflows/baseline.yml)

For a named substitution the judge measures the edit alone, with the opening reference, with the current best archive proof and with selected earlier alternatives. To try a joint edit, add `-- combine: #1 #7` as the first line in the fence, before your Lean source or the single `reuse` instruction. Replace the numbers with earlier accepted issues on distinct targets. Missing or incompatible nominations leave the standalone result eligible. The board lists the smallest complete proof found in the trials it runs. Dependencies shared by multiple replacements are charged once. The accepted-entry table separates the standalone measurement against the untouched archive from the certified points actually awarded. Unreachable declarations have a standalone saving of zero.

A direct unconditional proof competes with the entire incumbent. A `prime-window` entry and a `prime-supply` entry can also complete RH together. A pair pays for both proofs, shared course definitions once and their four-node application theorem. The fast judge can measure the joint saving once both halves arrive. Awarding official credit requires a complete audit of that composition. The standalone `window-logic` exercise earns zero whole-proof points.

Local records count distinct expressions across the answer’s type, proof and all submitted helper types and bodies together, with the pinned course library available. Each account has one local best per target. The site also publishes the complete record history, exact sizes and attribution in [scores.json](https://nikete.github.io/rh_golf/scores.json).

## Judge and publication

1. An `issues.opened` workflow on the trusted default branch reads the event file as data. Entrants submit declarations, never workflows, scores or checkout instructions.
2. An unprivileged Docker process with a read-only course, no network or credentials, 2 CPUs, 6 GiB RAM, and a temporary writable filesystem elaborates the source. A trusted extractor emits a data-only certificate. The host gives the certificate to a separate verifier.
3. The verifier starts from the pinned environment for the target, reconstructs expressions, and asks Lean’s kernel to check each theorem, safe definition and proved opaque helper. A final theorem with the locked target type uses the submitted `Entry.answer`. The transitive axiom allowlist is `propext`, `Classical.choice` and `Quot.sound`. The verifier computes both the local node count and the integrated declaration weights. The publisher receives the submitted source as text and the verifier’s receipt.
4. A fresh job validates accepted receipts and records the original submission on `golf-scores` with fast-forward-only retries. A serialized Pages workflow renders the latest complete ledger to static HTML and JSON. Public entry runs cannot overwrite another entrant’s score. The site serves static files. An optional script copies the agent prompt to the clipboard. Re-running a completed entry is idempotent.

A portfolio manifest may contain up to 1,260,000 substitutions, 32 MiB compressed and 160 MiB expanded. Custom Lean entry limits are 48 KiB of source, 8 MiB of certificate, 100,000 encoded expression nodes, 1,000 declarations, six minutes for elaboration and four for replay. New inductive families are outside the certificate format for season 1. Existing core/course inductives are supported. A compact unconditional solution is eligible under the same limits as other submissions. GitHub account identity does not guarantee one unique person. Equal local sizes share a local rank.

## Run and reproduce

On x86-64 Ubuntu, a clean checkout needs git, curl, Python 3, zstd, Docker and room for the pinned Lean release and targeted Mathlib cache. The public GitHub runner is the reference environment.

```sh
bash judge/prepare.sh
docker pull "$(cat judge/image.txt)"
python3 judge/run.py --target Formalism.VW.rh_of_right --source examples/reflection.lean --output .out/result.json
python3 -m unittest discover -s tests -v
bash judge/snapshot.sh
python3 -m http.server 8000 -d public
```

For a fresh fork, enable Issues, select **GitHub Actions** as the Pages publishing source and run **Publish standings**. The publisher also supports an existing Pages site served from the root of `gh-pages`. In that mode it pushes the generated site and requests the Pages build. Both modes produce a downloadable HTML artifact. Changes to the course or judge run both references through the public candidate path and test that admitted and wrong-target proofs are rejected. The original two receipts retain their local scores. The reference workflow replays both historical sources with the versioned whole-proof metric and checks their certificate hashes.

## Design precedents

[Code Golf](https://code.golf/stats) reports over 12,000 golfers and 570,000 submissions. Its [per-hole scoring](https://code.golf/about) rewards repeated improvements and ties. [Project Euler](https://projecteuler.net/recent) maintains a numbered mathematical problem archive with problem-level solve counts. [lean.golf](https://deancureton.com/projects/lean-golf/) already demonstrates short Lean proof challenges with GitHub identity. RH Golf uses its own putting-green mark, scorecards and a critical-strip diagram. Public entries make each reduction inspectable.
