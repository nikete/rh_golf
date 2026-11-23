# External RH simplification projects

Survey started 22 November 2026. This directory follows public work on shortening Alpöge’s Lean proof, including component challenges, unpublished-in-Golf proof edits, and proposed mathematical shortcuts. The tournament measures reachable expression nodes for ordinary RH. Scores in tokens, files or lines belong to the source project.

| Project | What to import or watch |
|---|---|
| [VerifyTask](https://riemann.verifytask.cn/) / [Bohrium challenge](https://play.bohrium.com/challenges/lean-4-verification-rh-core-pillar-1-5-classical-z-c7f72729) | Five unconditional pillars plus full RH. The [live board](https://lean.claude-en.com/api/board) showed 1,019 component submissions across 25 component challenges on 23 November at 13:47 UTC. Its full-RH card still reported the original 980,408,459 characters. The Core 1 leader, Bohrium attempt 101164, reported 997 tokens. The board supplied a description and score; importing that revision requires its complete Lean source. |
| [Yin-Kai Yu’s zero-free region](https://github.com/YinkaiYu/riemann-hypothesis-zero-free-region-lean4) and [compression toolkit](https://github.com/YinkaiYu/rh-compression-toolkit) | Tracks successive Core 1 proofs and Core 5 experiments. [Upstream PR 83](https://github.com/leanprover-community/riemann-hypothesis/pull/83) ports the single-file zero-free-region proof to the upstream project. |
| [Lean community](https://github.com/leanprover-community/riemann-hypothesis/pulls) | Individual PRs listed below. Merged, open, and superseded changes can overlap. |
| [GRH simplification drive](https://github.com/ShivMunagala/grh-simplification-drive) | Publishes patches and measurements. Reported 58 changes and 162,634,031 fewer written-out term nodes on 23 November across its five-target cone. Reprice for ordinary RH. |
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
| [QRH Catalogue](https://github.com/HaileyStorm/QRH-Catalogue/blob/44824138c975e34552d35e314cda60b32ad346b5/generated/DIRECTORY.md) | Index of reusable components with source provenance. Its [RiemannGaussian integration](https://github.com/dbsanfte/RiemannGaussian/pull/1) links 18 records. |

## 23 November 2026 imports

All four single substitutions passed the issue judge with portable witnesses. Each combined measurement used the independent delta checker and the [certified #18 manifest](https://github.com/nikete/rh_golf/issues/18), SHA-256 `520dcf8e1a1165502e32d0976ad6872545f9bf4116266efcadd8d6ded5a5f82d`. The base measured 2,369,269,797 nodes. None of the four overlays qualified as a new record.

| Pinned source | Entry | Certified standalone nodes | Official points | Locally measured combined nodes |
|---|---|---:|---:|---:|
| [Archimedean base change](https://github.com/Visio-Vanitas/riemann-hypothesis/blob/c5bfbbf9e1d83ce7b43b7890dcb9f17858cc68b3/src/Development/WeilBound/RepresentationTheoryGL/ArchimedeanBaseChange/ArchimedeanBaseChangeProof/SatakeExponents/BciOf.lean) | [#30 verdict](https://github.com/nikete/rh_golf/issues/30#issuecomment-7103119797) | 2,502,029,813 | 0 | 2,369,269,803 (6 more) |
| [Gauss–Manin periods](https://github.com/leanprover-community/riemann-hypothesis/blob/003526389ad0e26c6e5682565ce57f273e7f52bf/src/Development/AbelianVarietyTheory/Proofs/DivisorProofs/ImportsSideExtra.lean) | [#31 verdict](https://github.com/nikete/rh_golf/issues/31#issuecomment-7103116276) | 2,501,810,342 | 0 | 2,369,269,797 (equal) |
| [Weil operator D](https://github.com/by-eureka/riemann-hypothesis/blob/709c6feee562d2ab2ff7b16b51345c67a70c801a/src/CompanionTheory/AutomorphicTheory/ThetaDilations/SqPosOfNe.lean#L91) | [#34 verdict](https://github.com/nikete/rh_golf/issues/34#issuecomment-7103187839) | 2,502,222,852 | 0 | 2,369,270,845 (1,048 more) |
| [Weil operator uniqueness](https://github.com/by-eureka/riemann-hypothesis/blob/709c6feee562d2ab2ff7b16b51345c67a70c801a/src/CompanionTheory/AutomorphicTheory/ThetaDilations/SqPosOfNe.lean#L125) | [#35 verdict](https://github.com/nikete/rh_golf/issues/35#issuecomment-7103184283) | 2,502,208,804 | 0 | 2,369,291,502 (21,705 more) |

- [PR 119](https://github.com/leanprover-community/riemann-hypothesis/pull/119) repeats the Gauss–Manin redirect from PR 100. #31 credits the earlier artifact. The Čech pullback donor exists in the pinned index, but the PR's target name is absent. Deferred until mapped to a matching pinned declaration.
- [PR 54, orbit bound](https://github.com/by-eureka/riemann-hypothesis/blob/709c6feee562d2ab2ff7b16b51345c67a70c801a/src/CompanionTheory/AutomorphicTheory/ThetaDilations/SqPosOfNe.lean#L145) did not pass the exact-signature check. Testing the actual Lean application with its hypotheses is still open.
- [rh-trim](https://github.com/keithadler/rh-trim/blob/main/BUILD-STATUS.md) reported an 8.2% source-line reduction while repairing its build. Deferred pending a checkable proof edit. [Riemann@home](https://github.com/Riemann-at-home/riemann-at-home) coordinates baseline builds. [RH Proof Lab](https://github.com/eitamatgithub/rh-proof-lab) maps the argument.
- [#32](https://github.com/nikete/rh_golf/issues/32) retries #22 with explicit complex and real types. [#33](https://github.com/nikete/rh_golf/issues/33) retries #24 with simplification of the first power. Both preserve the upstream statements and helpers.

## Entries sent to RH Golf

| Source change | Ordinary-RH target | Entry and evidence |
|---|---|---|
| [Covariance formula reuse](https://github.com/leanprover-community/riemann-hypothesis/pull/92/commits/bb1ffc43837cba8e5fad630e6688d45dd818a3ea) | GlobalTheory.CovNFormulaPf.main | [#19, portable witness](https://github.com/nikete/rh_golf/issues/19). Certified 2,500,874,748 nodes, 0 points. Same target and donor as [#14](https://github.com/nikete/rh_golf/issues/14). |
| [Reflection proof](https://github.com/leanprover-community/riemann-hypothesis/pull/95/commits/018e327c93d07383f5542b97741ca17548db2a7e) | Formalism.VW.rh_of_right | [#20](https://github.com/nikete/rh_golf/issues/20). Measured, provisional gain 0. |
| [Bohrium Core 1 zero-free region port](https://github.com/leanprover-community/riemann-hypothesis/pull/83/commits/92e1668af9185779557a28ce4983f28e5d12b41f) | Formalism.ZF.zeroFreeRegion | [#21](https://github.com/nikete/rh_golf/issues/21). Runner lacked ripgrep during module lookup. Revised entry #22 supplies the pinned module explicitly. |
| [Core 1 retry](https://github.com/leanprover-community/riemann-hypothesis/pull/83/commits/92e1668af9185779557a28ce4983f28e5d12b41f) | `Formalism.ZF.zeroFreeRegion` | [#22](https://github.com/nikete/rh_golf/issues/22#issuecomment-7080595543). Lean elaboration failed, including an unresolved `Graph.re`. |
| [Lean community PR 75](https://github.com/YinkaiYu/riemann-hypothesis/blob/4938a86c3e68095277b498f3b92e2bd4d2fda3ec/src/Formalism/ZeroFreeRegion/ZetaLogDerivativeBounds/ThreeFourOne.lean#L9) | `Formalism.ZF.mertensInequality` | [#23](https://github.com/nikete/rh_golf/issues/23#issuecomment-7080580597). Measured 2,502,220,693 nodes, provisional gain 0. |
| [Lean community PR 87](https://github.com/graohene10-spec/riemann-hypothesis/blob/8e92b2be254a03fa837ad68a96e2be73b92ef8ef/src/Development/AbelianVarietyTheory/Definitions/GlobalTwisting/FamilyClassSevenDutiesAndStableLattices.lean#L64) | `GlobalTheory.EX.DQ.TwAllAt.twAt` | [#24](https://github.com/nikete/rh_golf/issues/24#issuecomment-7080952572). Rejected with a Lean type mismatch. |
| [Lean community PR 94](https://github.com/hhh2210/riemann-hypothesis/blob/ae11f0f2b01356117a3acb5a4fb888c322bc7b8e/src/Development/AutomorphicArithmetic/IntegralCasts/CapelliIdentities/NormIndexQuadratic.lean#L39) | `UpperTheory.Reformulated.B.NormIndexQuadratic.glob_neg_one` | [#25](https://github.com/nikete/rh_golf/issues/25). Submitted, awaiting verdict. |
| [Simplification drive, change 33](https://github.com/ShivMunagala/grh-simplification-drive/commit/fff031930c9bf66bc2219b22552f38d3f2cd341b) | `GlobalTheory.RowChain.iter_chain` | [#26](https://github.com/nikete/rh_golf/issues/26#issuecomment-7080609160). Mathlib cache preparation failed. The [second attempt](https://github.com/nikete/rh_golf/issues/26#issuecomment-7084235296) hit the same cache failure. |
| [Lean community PR 54](https://github.com/by-eureka/riemann-hypothesis/blob/49d5c0357d6d23bead82db4562fe07ad31544370/src/CompanionTheory/AutomorphicTheory/ThetaDilations/Nuabs.lean#L82) | `CompanionTheory.PlacePermOperatorBicommutantSpan.unf` | [#27](https://github.com/nikete/rh_golf/issues/27#issuecomment-7080583807). Certified 2,502,223,953 nodes, 0 marginal points. |
| [Lean community PR 54](https://github.com/by-eureka/riemann-hypothesis/blob/49d5c0357d6d23bead82db4562fe07ad31544370/src/CompanionTheory/AutomorphicTheory/ThetaDilations/Nuabs.lean#L85) | `CompanionTheory.PlacePermOperatorBicommutantSpan.nuabs` | [#28](https://github.com/nikete/rh_golf/issues/28#issuecomment-7080582424). Certified 2,502,222,364 nodes, 0 marginal points. |
| [Lean community PR 68](https://github.com/leanprover-community/riemann-hypothesis/pull/68/commits/37e3cd06d3bc65c74b9496adfea9f9827e727fbf) | `GlobalTheory.automorphicFormsFiniteGL` | [#29](https://github.com/nikete/rh_golf/issues/29#issuecomment-7080585733). Certified 2,500,186,240 nodes, 0 marginal points. |

### Deferred findings and overlaps

- [Pi’s Bohrium attempt 97307](https://lean.claude-en.com/api/attempt/97307) reports 2,031 Core 1 tokens. Its public diff is marked truncated and shows only 117 added lines of the 221-line solution. Awaiting complete source for this distinct attempt.
- [PR 68's imported substitution (#29)](https://github.com/nikete/rh_golf/issues/29#issuecomment-7080585733) saved 2,041,028 nodes on the archive. We also replaced the corresponding substitution in [record #18](https://github.com/nikete/rh_golf/issues/18#issuecomment-7077199636) and ran the pinned delta checker. Both proofs measured 2,369,269,797 nodes, a local combined gain of zero. Both theorems in #18 already use the same third proof.
- PRs 54 and 87 each contain additional edits. The rows above cover individual declarations only. The 31-module principal-character route and the conditional Principia reduction remain catalogued above.

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

## Combined tests of earlier entries against #18

All 26 proof-entry issues through #29 were reviewed across open and closed states. Issues #3–5 were bounties. The base is [#18](https://github.com/nikete/rh_golf/issues/18#issuecomment-7077199636), certified at **2,369,269,797** reachable nodes. Each row is a separate local comparison with that same base. A positive saving means fewer nodes. Alternatives for the same theorem are mutually exclusive.

| Added to #18 | Combined nodes | Nodes saved | Finding |
|---|---:|---:|---|
| [#25](https://github.com/nikete/rh_golf/issues/25#issuecomment-7080655998) | 2,368,941,581 | 328,216 | Quadratic norm proof from upstream PR 94. |
| [#6](https://github.com/nikete/rh_golf/issues/6#issuecomment-7062851967) | 2,369,263,488 | 6,309 | Best earlier reflection proof on this base. |
| [#1](https://github.com/nikete/rh_golf/issues/1#issuecomment-7060408439) | 2,369,263,493 | 6,304 | Alternative reflection proof. |
| [#20](https://github.com/nikete/rh_golf/issues/20#issuecomment-7080218629) | 2,369,265,301 | 4,496 | Imported reflection proof from upstream PR 95. |
| [#6](https://github.com/nikete/rh_golf/issues/6#issuecomment-7062851967), [#25](https://github.com/nikete/rh_golf/issues/25#issuecomment-7080655998) together | **2,368,935,272** | **334,525** | Compatible in the measured graph. A complete linked export and audit are required for official credit. |
| [#23](https://github.com/nikete/rh_golf/issues/23#issuecomment-7080580597) | 2,369,283,470 | −13,673 | Grew the incumbent despite saving 6,575 nodes on the original. |
| [#7](https://github.com/nikete/rh_golf/issues/7#issuecomment-7064550379), [#8](https://github.com/nikete/rh_golf/issues/8#issuecomment-7064597387), [#9](https://github.com/nikete/rh_golf/issues/9#issuecomment-7064563142), [#10](https://github.com/nikete/rh_golf/issues/10#issuecomment-7064562098), [#11](https://github.com/nikete/rh_golf/issues/11#issuecomment-7064566006), [#12](https://github.com/nikete/rh_golf/issues/12#issuecomment-7064564391), [#13](https://github.com/nikete/rh_golf/issues/13#issuecomment-7064566577), [#14](https://github.com/nikete/rh_golf/issues/14#issuecomment-7064565320), [#16](https://github.com/nikete/rh_golf/issues/16#issuecomment-7064563658), [#19](https://github.com/nikete/rh_golf/issues/19#issuecomment-7080205532) | 2,369,269,797 each | 0 | Their individual replacements already have the same cost and dependencies in #18. |
| [#15](https://github.com/nikete/rh_golf/issues/15#issuecomment-7064564694), [#27](https://github.com/nikete/rh_golf/issues/27#issuecomment-7080583807), [#28](https://github.com/nikete/rh_golf/issues/28#issuecomment-7080582424), [#29](https://github.com/nikete/rh_golf/issues/29#issuecomment-7080585733) | 2,369,269,797 each | 0 | Each distinct overlay measured equal to the base. The full bundle nominated in #16 also tied. |
| [#17](https://github.com/nikete/rh_golf/issues/17#issuecomment-7064690557) | — | — | Merging the complete manifests produced a dependency cycle under both choices of precedence for conflicting targets. |
| [#18](https://github.com/nikete/rh_golf/issues/18#issuecomment-7077199636) | 2,369,269,797 | 0 | Base manifest replay. |
| [#2](https://github.com/nikete/rh_golf/issues/2#issuecomment-7060431972) | — | — | Standalone window-logic exercise. No ordinary-RH substitution is specified. |
| [#21](https://github.com/nikete/rh_golf/issues/21#issuecomment-7080218527), [#22](https://github.com/nikete/rh_golf/issues/22#issuecomment-7080595543) | — | — | First runner lacked ripgrep. The revised Core 1 entry failed Lean elaboration, including an unresolved `Graph.re`. |
| [#24](https://github.com/nikete/rh_golf/issues/24#issuecomment-7080952572) | — | — | Lean rejected the replacement at a type mismatch. |
| [#26](https://github.com/nikete/rh_golf/issues/26#issuecomment-7080609160) | — | — | Mathlib cache preparation failed before proof checking. The [second attempt](https://github.com/nikete/rh_golf/issues/26#issuecomment-7084235296) hit the same cache failure. |

The replay used the [#18 manifest](https://github.com/nikete/rh_golf/issues/18), the pinned signature index and dependency graph, and the [score receipts](https://github.com/nikete/rh_golf/tree/golf-scores/ledger/1). For each comparable entry we replaced its target in the incumbent, retained the other edits and checked the joint graph for cycles and reachable cost. For custom Lean, the inputs were the published proof footprints and archive dependencies. These mixed results are local measurements. The existing issue judge certifies exact-reuse portfolios and requires full-export evidence for mixed proofs.

## Measuring a finding against the record

For each finding, record its standalone verdict and test what it saves when added to the current certified ordinary-RH proof. A zero-point verdict alone leaves that second question open. Link the incumbent issue, the exact candidate revision and the combined verdict. Mark a local measurement as local until the issue judge certifies the combined entry.

For an exact-reuse record, download the base manifest pinned in its issue. Run the following from the repository root with the archive graph installed. Use a new output path. For a candidate portfolio, replace `--target TARGET --donor DONOR` with `--manifest candidate.jsonl.gz`.

```sh
python3 judge/compare_reuse.py --graph .out/archive-graph \
  --base incumbent.jsonl.gz --base-sha256 BASE_DIGEST \
  --target TARGET --donor DONOR --output combined.jsonl.gz
```

The checker measures the base, replaces each candidate target's donor while retaining the other substitutions, checks the joint proof, and reports the difference. A positive result is ready for witness generation and submission under the finding's URL. If the joint proof is rejected, record the checker reason. If the incumbent or candidate needs an unsupported proof format, mark the combination unmeasured. Recheck against the latest certified record before filing an improvement.

## Entering an external result

Use the specific finding’s public HTTPS permalink as its display name. Prefer a commit-pinned file link or the individual submission URL. In an issue opened by the repository owner, put `Imported from URL` on its own first line, then the ordinary fenced entry and any portable proof. The ledger retains the submitting GitHub account. The official judge determines eligibility, whole-proof size and marginal points. Search existing entries by target, source and origin before opening an issue. Keep newer revisions distinct when their proof changes.
