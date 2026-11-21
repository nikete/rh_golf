# RH Golf

A points-only Lean proof league for the Riemann hypothesis. Play a hole by submitting a GitHub issue. GitHub Actions checks the proof and updates a static GitHub Pages scoreboard.

**[Play the course](https://nikete.github.io/rh_golf/) · [Open an entry](https://github.com/nikete/rh_golf/issues/new?template=entry.md) · [Judge runs](https://github.com/nikete/rh_golf/actions/workflows/play.yml)**

| Hole | Fixed proposition | First target to beat |
| --- | --- | --- |
| `window-logic` | Incompatible good and bad windows exclude a hypothetical zero, under the stated hypotheses. | 104 nodes |
| `reflection` | Nonvanishing of zeta right of the critical line implies Mathlib’s RH. | 2,297 nodes |
| `prime-window` | A one-sided bound for the named centered prime sum on arbitrarily late three-halves power windows implies RH. | Open |
| `prime-supply` | Prove the prime-window bound for ordinary primes. This and a proof of `prime-window` compose to give unconditional RH. | Open |
| `riemann` | Mathlib’s unconditional `RiemannHypothesis`. | Open |

The pinned [course propositions](League/Targets.lean) contain no solutions. [Reference proofs](examples/) set initial scores and never appear as players. The archived paper’s full certificate exceeds this hosted course’s limits. The conditional prime-window target uses the statistic and quantifiers of the [published analytic reduction](https://github.com/nasqret/riemann-rev/blob/d53b3804bd013df4cf9af3b4087728148c90c9bd/references/archive-bridges/WindowBridge.lean) and the [original centered sum](https://github.com/Deicyde/riemann-hypothesis/blob/40e56bab026552e089d7afcfeff08d2defb9c005/src/Development/AutomorphicArithmetic/DedekindLFunctions/CharFamily.lean). The reflection reference uses the completed zeta functional equation. The first hole adapts the [reading project’s window logic](https://github.com/nasqret/riemann-rev/blob/d53b3804bd013df4cf9af3b4087728148c90c9bd/lean/Reading/WindowLogic.lean).

The [proof map](https://nikete.github.io/rh_golf/proof.html) describes how the two prime-window holes compose. The course’s reflection proof uses the symmetry of completed zeta and takes 2,297 nodes. Applying the same judge to the original reflection argument gives 7,404 nodes, a measured saving of 69.0% for this step. The full archive has separate dependencies. The [reference workflow](.github/workflows/course.yml) reproduces the comparison.

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

The judge counts distinct Lean expression nodes reachable from the final theorem’s type and proof, expanding any submitted helper types and bodies. Pinned Lean and the course library are free. The metric strips metadata and binder names. Numerals and strings are literal nodes. Both repeated subterms and transitive helper dependencies are counted once. Unused helpers earn nothing. This measures a local reduction's Lean representation under the course library. Its savings in the complete archived RH proof require a separate integration measurement.

Per hole, par is the smallest accepted node count including any course reference. Points are `floor(1000 × par / personal_best)`. One score per GitHub account per hole counts toward the total. Ties share points and rank. All points are recalculated when a record improves.

## Judge and publication

1. An `issues.opened` workflow on the trusted default branch reads the event file as data. Entrants submit declarations, never workflows, scores or checkout instructions.
2. An unprivileged Docker process with a read-only course, no network or credentials, 2 CPUs, 6 GiB RAM, and a temporary writable filesystem elaborates the source. A trusted extractor emits a data-only certificate. The host gives the certificate to a separate verifier.
3. The verifier starts with **only the pinned course environment**, reconstructs expressions, and asks Lean’s kernel to check each theorem, safe definition and proved opaque helper. A final theorem with the locked target type uses the submitted `Entry.answer`. The transitive axiom allowlist is `propext`, `Classical.choice` and `Quot.sound`. The verifier computes the node count itself. Arbitrary source text, compiled entrant modules and entrant output logs never enter the publisher.
4. A fresh job validates accepted receipts and records the original submission on `golf-scores` with fast-forward-only retries. A serialized Pages workflow renders the latest complete ledger to static HTML and JSON. Public entry runs cannot overwrite another entrant’s score. The site uses no runtime API, database, token, JavaScript or external judge. Re-running a completed entry is idempotent.

Limits per entry are 48 KiB of source, 8 MiB of certificate, 100,000 encoded expression nodes, 1,000 declarations, six minutes for elaboration and four for replay. New inductive families are outside the certificate format for season 1. Existing core/course inductives are supported. A compact unconditional solution is eligible under the same limits as the other holes. GitHub account identity does not guarantee one unique person. Identical public proofs may tie.

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

For a fresh fork, enable Issues, select **GitHub Actions** as the Pages publishing source and run **Publish standings**. The publisher also supports an existing Pages site served from the root of `gh-pages`. In that mode it pushes the generated site and requests the Pages build. Both modes produce a downloadable HTML artifact. Changes to the course or judge run both references through the public candidate path and test that admitted and wrong-target proofs are rejected. Start a new season when changing the course library, metric or target definitions.

## Design precedents

[Code Golf](https://code.golf/stats) reports over 12,000 golfers and 570,000 submissions. Its [per-hole scoring](https://code.golf/about) rewards repeated improvements and ties. [Project Euler](https://projecteuler.net/recent) maintains a numbered mathematical problem archive with problem-level solve counts. [lean.golf](https://deancureton.com/projects/lean-golf/) already demonstrates short Lean proof challenges with GitHub identity. RH Golf uses its own putting-green mark, scorecards and a critical-strip diagram. A seasonal points table and open source entries make reductions inspectable.

[Code Golf Stack Exchange’s standing bounties](https://codegolf.meta.stackexchange.com/questions/5243/list-of-bounties-with-no-deadline) offer reputation to anyone who beats a specified score. RH Golf keeps the open challenge and makes the award automatic.
