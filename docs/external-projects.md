# External RH simplification projects

Survey started 22 November 2026. This directory follows public work on shortening Alpöge’s Lean proof, including component challenges, unpublished-in-Golf proof edits, and proposed mathematical shortcuts. The tournament measures reachable expression nodes for ordinary RH. Scores in tokens, files or lines belong to the source project.

| Project | What to import or watch |
|---|---|
| [VerifyTask](https://riemann.verifytask.cn/) / [Bohrium challenge](https://play.bohrium.com/challenges/lean-4-verification-rh-core-pillar-1-5-classical-z-c7f72729) | Five unconditional pillars plus full RH. The dashboard showed 241 runs on its progress curve, 67 breakthroughs and 48% combined token compression. Its full-RH card still showed the original character count. Follow individual attempts and public source patches. |
| [Yin-Kai Yu’s zero-free region](https://github.com/YinkaiYu/riemann-hypothesis-zero-free-region-lean4) and [compression toolkit](https://github.com/YinkaiYu/rh-compression-toolkit) | Tracks successive Core 1 proofs and Core 5 experiments. [Upstream PR 83](https://github.com/leanprover-community/riemann-hypothesis/pull/83) ports the single-file zero-free-region proof to the upstream project. |
| [Lean community](https://github.com/leanprover-community/riemann-hypothesis/pulls) | Individual PRs listed below. Merged, open, and superseded changes can overlap. |
| [GRH simplification drive](https://github.com/ShivMunagala/grh-simplification-drive) | Publishes patches and measurements. Reported 31 changes and 84,889,166 fewer written-out term nodes across its five-target cone. Reprice for ordinary RH. |
| [RH Lean Dissection](https://github.com/thekeunpie-hash/rh-lean-dissection) / [kernel backbone](https://github.com/thekeunpie-hash/rh-kernel-backbone) | Refactors behind upstream PRs 60, 65 and 71, plus dependency analysis. Credit the same patch once. |
| [RiemannGaussian](https://github.com/dbsanfte/RiemannGaussian) | Principal-character route to ordinary RH using 31 new modules. [Upstream PR 38](https://github.com/leanprover-community/riemann-hypothesis/pull/38) is a candidate for complete-export checking. |
| [Principia collaborative RH project](https://principia-math.com/projects/d16ab288ed353bc5b10e292ace0ddbc1) | Conductor-one conditional reductions and a signal bound in [PR 12](https://github.com/leanprover-community/riemann-hypothesis/pull/12). A component can enter when it matches a Golf target with all required hypotheses. |
| [nil-commits blueprint](https://github.com/nil-commits/alpoge-rh-verification-blueprint) / [golf repo](https://github.com/nil-commits/alpoge-rh-golf) | Consolidated top-level proof in SimplifiedMain.lean plus import pruning. The two READMEs describe the same artifacts. |
| [onroids](https://github.com/onroids/riemann-hypothesis) | Separate review queue targeting the dev branch. |
| [DeepTheory Labs](https://deeptheory-labs.github.io/GRH/) | Staged simplifications and proof graphs. The published site identified simp-01 as planned. |
| [Riemann proof atlas](https://github.com/nasqret/riemann-proof-atlas) / [reading project](https://nasqret.github.io/riemann-rev/book/_static/blueprint/atlas-blueprint.pdf) | Component interfaces and checked implications with explicit assumptions. |
| [Three simplifications](https://github.com/twinheterodox/three-simplifications-dirichlet-grh) | Mathematical improvements to prime-sum and lattice arguments. Requires formalization. |
| [GRH distillation](https://github.com/JoseBrox/GRH_distillation) | Manuscripts and source maps, with the decisive uniform estimate still open in the distillation. |
| [GRH proof synthesis](https://github.com/OssaBellator/grh-proof-synthesis) | Preliminary comparison of Alpöge and Masullo, including a toy Lean lemma. |
| [MIT verification](https://math.mit.edu/~drew/grh/), [community comparator](https://github.com/leanprover-community/riemann-hypothesis), [independent replay](https://github.com/rohanarun/alpoge-rh-replay) | Baseline evidence and replay infrastructure. |
| [Lean Explorer](https://github.com/rithn/riemann-lean-reader), [tamnd source mirror](https://github.com/tamnd/riemann-lean) | Navigation, provenance and discovery of new forks. |

## Entries sent to RH Golf

| Source change | Ordinary-RH target | Entry and evidence |
|---|---|---|
| [Covariance formula reuse](https://github.com/leanprover-community/riemann-hypothesis/pull/92/commits/bb1ffc43837cba8e5fad630e6688d45dd818a3ea) | GlobalTheory.CovNFormulaPf.main | [#19, portable witness](https://github.com/nikete/rh_golf/issues/19). Local standalone count 2,500,874,748 nodes. |
| [Reflection proof](https://github.com/leanprover-community/riemann-hypothesis/pull/95/commits/018e327c93d07383f5542b97741ca17548db2a7e) | Formalism.VW.rh_of_right | [#20, judge verdict thread](https://github.com/nikete/rh_golf/issues/20) |
| [Bohrium Core 1 zero-free region port](https://github.com/leanprover-community/riemann-hypothesis/pull/83/commits/92e1668af9185779557a28ce4983f28e5d12b41f) | Formalism.ZF.zeroFreeRegion | [#21, judge verdict thread](https://github.com/nikete/rh_golf/issues/21) |

## Upstream changes to examine

- [#4](https://github.com/leanprover-community/riemann-hypothesis/pull/4) chore: minimize imports
- [#8](https://github.com/leanprover-community/riemann-hypothesis/pull/8) simplify Main imports and remove six unused modules
- [#9](https://github.com/leanprover-community/riemann-hypothesis/pull/9) remove redundant imports and heartbeat overrides
- [#10](https://github.com/leanprover-community/riemann-hypothesis/pull/10) simplify generated proof fallbacks
- [#12](https://github.com/leanprover-community/riemann-hypothesis/pull/12) A conductor-one RH reduction and a signal bound found through Principia's collaborative project
- [#38](https://github.com/leanprover-community/riemann-hypothesis/pull/38) Specialize ordinary RH to the principal character
- [#44](https://github.com/leanprover-community/riemann-hypothesis/pull/44) Simplify the shared five-theorem proof and reduce its Lean source by 1.54 million lines
- [#45](https://github.com/leanprover-community/riemann-hypothesis/pull/45) Prune unused top-level imports and 11,163 unreachable dead modules
- [#54](https://github.com/leanprover-community/riemann-hypothesis/pull/54) Golf the Riemann hypothesis proof one theorem at a time (3,361 fewer Lean lines)
- [#55](https://github.com/leanprover-community/riemann-hypothesis/pull/55) Remove declarations that are unused in the proof
- [#57](https://github.com/leanprover-community/riemann-hypothesis/pull/57) Simplify explicit typeclass dumps in 5 CapelliIdentities files
- [#58](https://github.com/leanprover-community/riemann-hypothesis/pull/58) Collapse 24,027 single-declaration thin re-export wrappers (stacked on #55)
- [#60](https://github.com/leanprover-community/riemann-hypothesis/pull/60) Simplify explicit typeclass dump in CapelliIdentities/FixPiIff.lean
- [#61](https://github.com/leanprover-community/riemann-hypothesis/pull/61) Collapse 5,544 more thin re-export wrappers — Wave 2 (stacked on #58)
- [#62](https://github.com/leanprover-community/riemann-hypothesis/pull/62) Shorten machine-dumped terms and reuse repeated proofs in 76 modules (stacked on #66)
- [#63](https://github.com/leanprover-community/riemann-hypothesis/pull/63) Consolidate 133,202 small sibling modules into 22,831 antichain bundles (−110,371 files, −67.1%)
- [#65](https://github.com/leanprover-community/riemann-hypothesis/pull/65) Simplify explicit typeclass dumps in 4 kernel-used CapelliIdentities files
- [#67](https://github.com/leanprover-community/riemann-hypothesis/pull/67) Remove proof syntax that was flagged unused by Lean's linters
- [#68](https://github.com/leanprover-community/riemann-hypothesis/pull/68) Share the rank-induction proof of GL finiteness (9,010 fewer Lean lines)
- [#70](https://github.com/leanprover-community/riemann-hypothesis/pull/70) Simplify explicit typeclass dumps in 5 more CapelliIdentities files
- [#71](https://github.com/leanprover-community/riemann-hypothesis/pull/71) chore: remove 66 backward.* options across 4 kernel-used scheme files
- [#74](https://github.com/leanprover-community/riemann-hypothesis/pull/74) Give four duplicated theorems a single defining module
- [#75](https://github.com/leanprover-community/riemann-hypothesis/pull/75) Share analytic proofs across zeta and Dirichlet L-functions (630 fewer Lean lines)
- [#76](https://github.com/leanprover-community/riemann-hypothesis/pull/76) Share the threshold argument in combined_weight_of_nested_sets
- [#82](https://github.com/leanprover-community/riemann-hypothesis/pull/82) Share stabilizer filtration and Hensel counts (414 fewer Lean lines)
- [#83](https://github.com/leanprover-community/riemann-hypothesis/pull/83) Zero-free region: replace the 34-file assembly with a self-contained 2,368-token proof (-89.1% normalized tokens)
- [#87](https://github.com/leanprover-community/riemann-hypothesis/pull/87) Shorten checked proofs across 816 Lean modules
- [#90](https://github.com/leanprover-community/riemann-hypothesis/pull/90) Golf proofs in si x ThetaBesselIsometries / BesselWaveGrids files (−344 lines)
- [#91](https://github.com/leanprover-community/riemann-hypothesis/pull/91) Combine five reviewed cleanup PRs (stacked on #66)
- [#92](https://github.com/leanprover-community/riemann-hypothesis/pull/92) Reuse the existing CovNFormula proof
- [#94](https://github.com/leanprover-community/riemann-hypothesis/pull/94) Reuse the quadratic Hasse norm theorem for the negative-one norm equation
- [#95](https://github.com/leanprover-community/riemann-hypothesis/pull/95) Simplify proofs in GammaFactorNonvanishing and ZeroFreeRegion (−824 lines)
- [#98](https://github.com/leanprover-community/riemann-hypothesis/pull/98) Minimize and privatize imports (stacked on #79)

## Entering an external result

Use the specific finding’s public HTTPS permalink as its display name. Prefer a commit-pinned file link or the individual submission URL. In an issue opened by the repository owner, put `Imported from URL` on its own first line, then the ordinary fenced entry and any portable proof. The ledger retains the submitting GitHub account. The official judge determines eligibility, whole-proof size and marginal points. Search existing entries by target, source and origin before opening an issue. Keep newer revisions distinct when their proof changes.
