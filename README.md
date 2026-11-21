# RH Golf

A points-only Lean proof league for the Riemann hypothesis. Play a hole by submitting a GitHub issue. GitHub Actions checks the proof and updates a static GitHub Pages scoreboard.

**[Play the course](https://nikete.github.io/rh_golf/) · [Open an entry](https://github.com/nikete/rh_golf/issues/new?template=entry.md) · [Judge runs](https://github.com/nikete/rh_golf/actions/workflows/play.yml)**

| Hole | Fixed proposition | Opening local record |
| --- | --- | --- |
| `window-logic` | Incompatible good and bad windows exclude a hypothetical zero, under the stated hypotheses. | 104 nodes |
| `reflection` | Nonvanishing of zeta right of the critical line implies Mathlib’s RH. | 2,297 nodes |
| `prime-window` | A one-sided bound for the named centered prime sum on arbitrarily late three-halves power windows implies RH. | Open |
| `prime-supply` | Prove the prime-window bound for ordinary primes. This and a proof of `prime-window` compose to give unconditional RH. | Open |
| `riemann` | Mathlib’s unconditional `RiemannHypothesis`. | Open |

The pinned [course propositions](League/Targets.lean) contain no solutions. [Reference proofs](examples/) set initial scores and never appear as players. The archived paper’s full certificate exceeds this hosted course’s limits. The conditional prime-window target uses the statistic and quantifiers of the [published analytic reduction](https://github.com/nasqret/riemann-rev/blob/d53b3804bd013df4cf9af3b4087728148c90c9bd/references/archive-bridges/WindowBridge.lean) and the [original centered sum](https://github.com/Deicyde/riemann-hypothesis/blob/40e56bab026552e089d7afcfeff08d2defb9c005/src/Development/AutomorphicArithmetic/DedekindLFunctions/CharFamily.lean). The reflection reference uses the completed zeta functional equation. The first hole adapts the [reading project’s window logic](https://github.com/nasqret/riemann-rev/blob/d53b3804bd013df4cf9af3b4087728148c90c9bd/lean/Reading/WindowLogic.lean).

The [proof map](https://nikete.github.io/rh_golf/proof.html) describes how the two prime-window holes compose. The course’s reflection proof uses the symmetry of completed zeta and takes 2,297 nodes. Applying the same judge to the original reflection argument gives 7,404 nodes, a measured saving of 69.0% for this step. The overall scoreboard follows the dependencies of the ordinary RH theorem itself. The [reference workflow](.github/workflows/course.yml) reproduces the comparison.

## Enter

Set a fresh issue's title to `[entry] <hole-id>`, with an optional description after the ID. Put the source in one fenced Lean block in the body. Include a theorem named `Entry.answer`. The prelude imports `League.Course`. Example for `window-logic`:

```lean
theorem Entry.answer : Golf.WindowLogic := by
  intro I later zero good bad supply oscillation disjoint hz
  obtain ⟨k, hk⟩ := oscillation hz
  obtain ⟨y, hy, hg⟩ := supply k
  exact disjoint y hg (hk y hy)
```

Every entry has an authenticated GitHub author, an immutable issue-open snapshot and a CI verdict. To improve a score, open a fresh issue. The leaderboard links the exact submitted source and CI receipt. AI-assisted entries are welcome.

## Score

**One point is one expression node removed from the smallest complete proof of ordinary RH.** A player’s percentage is their points divided by the original proof size. The board starts with the smaller of the archive and the course reflection proof. The course’s opening reduction is shown separately. Replaying accepted entries in issue-number order makes the sum of player credits exactly equal the subsequent reduction. Copies, ties and larger proofs earn zero. [Current totals and records](https://nikete.github.io/rh_golf/#progress)

The archived starting point is **2,502,227,268 nodes**. Of those, 7,651 disappear when the original reflection theorem is removed. The opening reference costs 2,328 to put back and saves 5,323. Entry #1 costs 1,061 and therefore earns **1,267 points**. The practice entry in #2 earns zero. [First reflection entry](https://github.com/nikete/rh_golf/issues/1) · [Practice entry](https://github.com/nikete/rh_golf/issues/2)

The baseline walks the types, proof bodies and dependencies of the exported `riemannHypothesis`, stopping at pinned Lean and Mathlib. Each reachable declaration is charged once. Within a declaration, distinct Lean expression nodes across the type and body count once. The original reflection theorem has a fixed interface and a measured set of dependencies that disappear on replacement. The replay kernel checks each candidate again at that interface and prices its reachable additions, including course definitions. The published archive is scanned for the baseline audit. Each entry reuses the audited, retained part of the proof. [Baseline and pinned input](judge/baseline.json) · [Reproduce the graph audit in Actions](.github/workflows/baseline.yml)

A direct unconditional proof competes with the entire incumbent. A `prime-window` entry and a `prime-supply` entry can also complete RH together. A pair pays for both proofs, shared course definitions once and their four-node application theorem. When both parts enter the winning route together they split the gain, with any odd node going to the earlier issue. A replacement of one component of the winning pair earns the entire incremental gain when the other component is retained. An unpaired half can earn credit later. The standalone `window-logic` exercise earns zero whole-proof points.

Local hole rankings continue to count distinct expressions across the answer’s type, proof and all submitted helper types and bodies together, with the pinned course library available. Each account has one local best per hole. The site also publishes the complete record history, exact sizes and attribution in [scores.json](https://nikete.github.io/rh_golf/scores.json).

## Judge and publication

1. An `issues.opened` workflow on the trusted default branch reads the event file as data. Entrants submit declarations, never workflows, scores or checkout instructions.
2. An unprivileged Docker process with a read-only course, no network or credentials, 2 CPUs, 6 GiB RAM, and a temporary writable filesystem elaborates the source. A trusted extractor emits a data-only certificate. The host gives the certificate to a separate verifier.
3. The verifier starts with **only the pinned course environment**, reconstructs expressions, and asks Lean’s kernel to check each theorem, safe definition and proved opaque helper. A final theorem with the locked target type uses the submitted `Entry.answer`. The transitive axiom allowlist is `propext`, `Classical.choice` and `Quot.sound`. The verifier computes both the local node count and the integrated declaration weights. Arbitrary source text, compiled entrant modules and entrant output logs never enter the publisher.
4. A fresh job validates accepted receipts and records the original submission on `golf-scores` with fast-forward-only retries. A serialized Pages workflow renders the latest complete ledger to static HTML and JSON. Public entry runs cannot overwrite another entrant’s score. The site uses no runtime API, database, token, JavaScript or external judge. Re-running a completed entry is idempotent.

Limits per entry are 48 KiB of source, 8 MiB of certificate, 100,000 encoded expression nodes, 1,000 declarations, six minutes for elaboration and four for replay. New inductive families are outside the certificate format for season 1. Existing core/course inductives are supported. A compact unconditional solution is eligible under the same limits as the other holes. GitHub account identity does not guarantee one unique person. Equal local sizes share a local rank.

## Run and reproduce

On x86-64 Ubuntu, a clean checkout needs git, curl, Python 3, zstd, Docker and room for the pinned Lean release and targeted Mathlib cache. The public GitHub runner is the reference environment.

```sh
bash judge/prepare.sh
docker pull "$(cat judge/image.txt)"
python3 judge/run.py --hole reflection --source examples/reflection.lean --output .out/result.json
python3 -m unittest discover -s tests -v
bash judge/snapshot.sh
python3 -m http.server 8000 -d public
```

For a fresh fork, enable Issues, select **GitHub Actions** as the Pages publishing source and run **Publish standings**. The publisher also supports an existing Pages site served from the root of `gh-pages`. In that mode it pushes the generated site and requests the Pages build. Both modes produce a downloadable HTML artifact. Changes to the course or judge run both references through the public candidate path and test that admitted and wrong-target proofs are rejected. The original two receipts retain their local scores. The reference workflow replays both historical sources with the versioned whole-proof metric and checks their certificate hashes.

## Design precedents

[Code Golf](https://code.golf/stats) reports over 12,000 golfers and 570,000 submissions. Its [per-hole scoring](https://code.golf/about) rewards repeated improvements and ties. [Project Euler](https://projecteuler.net/recent) maintains a numbered mathematical problem archive with problem-level solve counts. [lean.golf](https://deancureton.com/projects/lean-golf/) already demonstrates short Lean proof challenges with GitHub identity. RH Golf uses its own putting-green mark, scorecards and a critical-strip diagram. A seasonal points table and open source entries make reductions inspectable.

[Code Golf Stack Exchange’s standing bounties](https://codegolf.meta.stackexchange.com/questions/5243/list-of-bounties-with-no-deadline) offer reputation to anyone who beats a specified score. RH Golf keeps the open challenge and makes the award automatic.
