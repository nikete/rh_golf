# RH Golf

Choose a theorem or safe definition in the archived Lean proof of the Riemann hypothesis and submit a smaller replacement. One point is one node removed from the best complete proof. GitHub Actions judges submissions and publishes the static scoreboard.

**[Enter a proof](https://github.com/nikete/rh_golf/issues/new?template=entry.md) · [Leaderboard and bounties](https://nikete.github.io/rh_golf/) · [Explore the proof](https://nikete.github.io/rh_golf/proof.html)**

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

The full proof that set the local record in entry #6 is available to copy or improve. A direct proof can instead target `[entry] riemannHypothesis` with `theorem Entry.answer : RiemannHypothesis := …`. To find other targets, follow the proof terms from `riemannHypothesis` to `rhOfAll`, `allChi`, or deeper in the pinned source. [Entry #6](https://github.com/nikete/rh_golf/issues/6) · [Archive root](https://github.com/Deicyde/riemann-hypothesis/blob/40e56bab026552e089d7afcfeff08d2defb9c005/src/Main.lean) · [Dependency walkthrough](https://nikete.github.io/rh_golf/proof.html)

The judge locates the declaration’s defining module in the pinned source. If the name is ambiguous or generated, put a module hint before the Lean source, after any `-- combine:` line. For example, use `-- archive-module: Formalism.GammaFactorNonvanishing.RhOfRight`. A module is the file path under `src/` with dots in place of slashes and the `.lean` suffix removed. The kernel checks the named declaration’s actual interface. A replacement may use archive dependencies available in its environment. The dependency check rejects paths back to the declaration it replaces. The fast paths for `Formalism.VW.rh_of_right` and `riemannHypothesis` use the course environment by default. Include the explicit module hint if the replacement uses the original module’s archive imports.

In the archive environment, `theorem Entry.answer : type_of% @Fully.Qualified.theorem := …` copies the exact statement, including implicit arguments. Supply your own proof after `:=`. To use lemmas from another pinned archive module, add a leading `-- archive-import: Qualified.Module` line after any module hint.

Two RH-reachable theorems, `lam_copy` and `sigSpan_copy`, each contain over four million local nodes. Their pinned source lines, full declaration names and individual weights appear on the leaderboard. Building these modules from scratch may exceed the hosted runner’s time or memory limits. [Large proofs to shrink](https://nikete.github.io/rh_golf/#large-targets)

Every entry has an authenticated GitHub author, an immutable issue-open snapshot and a CI verdict. To improve a score, open a fresh issue. The leaderboard links the exact submitted source and CI receipt. AI-assisted entries are welcome.

### Reuse an existing theorem

If another theorem already proves the identical statement, title the issue with the target you are replacing. Put this single line in the issue’s Lean fence, substituting the donor’s full name.

```lean
reuse Fully.Qualified.Donor
```

The target and donor must both be theorems in the pinned export. The donor may come from the archive or Mathlib. The exported type expressions and ordered universe parameters must match exactly. The judge checks the export’s axiom allowlist, checks that the proposed reference creates no dependency cycle, and measures the RH proof with that reference in place. This path relies on the independently checked export and produces a `pinned-export-exact-reuse-v1` receipt. Custom Lean submissions are replayed by Lean’s kernel. [Pinned input](judge/baseline.json) · [Independent verification logs](https://math.mit.edu/~drew/grh/)

## Score

**One point is one expression node removed from the smallest complete proof of ordinary RH.** A player’s percentage is their points divided by the original proof size. The board starts with the smaller of the archive and the course reflection proof. The course’s opening reduction is shown separately. Replaying accepted entries in issue-number order makes the sum of player credits exactly equal the subsequent reduction. Copies, ties and larger proofs earn zero. [Current totals and records](https://nikete.github.io/rh_golf/#progress)

The archived starting point is **2,502,227,268 nodes**. Of those, 7,651 disappear when the original reflection theorem is removed. The opening reference costs 2,328 to put back and saves 5,323. Entry #1 costs 1,061 and therefore earns **1,267 points**. The practice entry in #2 earns zero. [First reflection entry](https://github.com/nikete/rh_golf/issues/1) · [Practice entry](https://github.com/nikete/rh_golf/issues/2)

The baseline walks the types, proof bodies and dependencies of the exported `riemannHypothesis`, stopping at pinned Lean and Mathlib. Each reachable declaration is charged once. Within a declaration, distinct Lean expression nodes across the type and body count once. The original reflection theorem has a fixed interface and a measured set of dependencies that disappear on replacement. The replay kernel checks each candidate again at that interface and prices its reachable additions, including course definitions. The published archive is scanned for the baseline audit. Each entry reuses the audited, retained part of the proof. [Baseline and pinned input](judge/baseline.json) · [Reproduce the graph audit in Actions](.github/workflows/baseline.yml)

For a named substitution the judge measures the edit alone, with the opening reference, with the current best archive proof and with selected earlier alternatives. To try a joint edit, add `-- combine: #1 #7` as the first line in the fence, before your Lean source or the single `reuse` instruction. Replace the numbers with earlier accepted issues on distinct targets. Missing or incompatible nominations leave the standalone result eligible. The board lists the smallest complete proof found in the trials it runs. Dependencies shared by multiple replacements are charged once. The accepted-entry table shows both the standalone saving against the untouched archive and the points actually earned against the incumbent. Unreachable declarations have a standalone saving of zero.

A direct unconditional proof competes with the entire incumbent. A `prime-window` entry and a `prime-supply` entry can also complete RH together. A pair pays for both proofs, shared course definitions once and their four-node application theorem. When both parts enter the winning route together they split the gain, with any odd node going to the earlier issue. A replacement of one component of the winning pair earns the entire incremental gain when the other component is retained. An unpaired half can earn credit later. The standalone `window-logic` exercise earns zero whole-proof points.

Local records count distinct expressions across the answer’s type, proof and all submitted helper types and bodies together, with the pinned course library available. Each account has one local best per target. The site also publishes the complete record history, exact sizes and attribution in [scores.json](https://nikete.github.io/rh_golf/scores.json).

## Judge and publication

1. An `issues.opened` workflow on the trusted default branch reads the event file as data. Entrants submit declarations, never workflows, scores or checkout instructions.
2. An unprivileged Docker process with a read-only course, no network or credentials, 2 CPUs, 6 GiB RAM, and a temporary writable filesystem elaborates the source. A trusted extractor emits a data-only certificate. The host gives the certificate to a separate verifier.
3. The verifier starts from the pinned environment for the target, reconstructs expressions, and asks Lean’s kernel to check each theorem, safe definition and proved opaque helper. A final theorem with the locked target type uses the submitted `Entry.answer`. The transitive axiom allowlist is `propext`, `Classical.choice` and `Quot.sound`. The verifier computes both the local node count and the integrated declaration weights. The publisher receives the submitted source as text and the verifier’s receipt.
4. A fresh job validates accepted receipts and records the original submission on `golf-scores` with fast-forward-only retries. A serialized Pages workflow renders the latest complete ledger to static HTML and JSON. Public entry runs cannot overwrite another entrant’s score. The site uses no runtime API, database, token, JavaScript or external judge. Re-running a completed entry is idempotent.

Limits per entry are 48 KiB of source, 8 MiB of certificate, 100,000 encoded expression nodes, 1,000 declarations, six minutes for elaboration and four for replay. New inductive families are outside the certificate format for season 1. Existing core/course inductives are supported. A compact unconditional solution is eligible under the same limits as other submissions. GitHub account identity does not guarantee one unique person. Equal local sizes share a local rank.

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

[Code Golf Stack Exchange’s standing bounties](https://codegolf.meta.stackexchange.com/questions/5243/list-of-bounties-with-no-deadline) offer reputation to anyone who beats a specified score. RH Golf keeps the open challenge and makes the award automatic.
