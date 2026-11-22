# A smaller proof of an elliptic-curve identity

`GlobalTheory.AddLaw.negDiagY_smul` states that scaling the two inputs of the projective elliptic-curve addition formula by `u` and `v` scales its negative Y-coordinate polynomial by `(u * v)^2`. The archived proof expands the homogeneous polynomial and uses `ring1`. The replacement expands the same definitions and applies Lean's `Lean.Grind.CommRing.Expr.eq_of_toPoly_eq` to the two reflected expressions. The kernel checks equality of the normalized polynomials. It uses `propext`, `Classical.choice`, and `Quot.sound`.

The archive graph charges 58,836 expression nodes for the old declaration itself. The local candidate has 6,206 distinct nodes in its type, proof and three generated simp helpers, a reduction of 52,630 by this comparison. I compiled the original target declaration and its source definitions under Lean 4.33.1 and the pinned Mathlib elliptic-curve imports, then compiled the complete entry with `type_of% @GlobalTheory.AddLaw.negDiagY_smul`. The other archived declarations in the file were unnecessary for this local test.

A custom Lean entry and a complete `reuse-file` portfolio follow separate competition routes. A combined score would require measuring and certifying the linked proof. On the exact graph of entry #18 the target remains reachable. Applying the eight archive dependencies of the checked term and the judge’s integrated charge of 6,398 private nodes projects 2,369,217,102 whole-RH nodes, 52,695 below #18’s 2,369,269,797. The 6,398 charge counts each reachable declaration separately. This mixed-route projection has not been certified and earns no points by itself.

To reproduce the public judge's check from the RH Golf checkout, save `negDiagY_smul-entry.lean` and run on Linux with Docker:

```sh
bash judge/prepare.sh
python3 judge/run.py --target GlobalTheory.AddLaw.negDiagY_smul \
  --source negDiagY_smul-entry.lean --output .out/negDiagY_smul.json
```

The source module is `Development.AbelianVarietyTheory.Proofs.HomogeneousIdeals.DiagZEqNegAddY` at archive revision `40e56bab026552e089d7afcfeff08d2defb9c005`. It imports Mathlib; a cold build needs the complete pinned Mathlib cache. The separate full-export audit is required for official custom-proof points.

## Six compatible replacements

The same method also handles scaling the X- and Z-coordinates and identifying all three diagonal formulas on equal inputs. All six original theorem groups remain reachable in #18. Each entry source is named `<theorem>-entry.lean`.

| Theorem in `GlobalTheory.AddLaw` | Original group nodes | Local candidate nodes | Integrated private nodes | Projected saving on #18 |
|---|---:|---:|---:|---:|
| `diagX_self` | 34,757 | 1,458 | 1,458 | 33,299 |
| `negDiagY_self` | 50,532 | 1,803 | 1,803 | 48,729 |
| `diagZ_self` | 17,460 | 924 | 924 | 16,536 |
| `diagX_smul` | 37,214 | 4,635 | 4,827 | 32,644 |
| `negDiagY_smul` | 58,836 | 6,206 | 6,398 | 52,695 |
| `diagZ_smul` | 25,875 | 3,696 | 3,888 | 22,244 |

The six Lean-checked terms have no shared course costs. The integrated column uses the judge’s `Golf.Footprint.measure`. Replacing all six groups in #18’s graph, with the archive dependencies of each checked term, yields **2,369,063,650 nodes**, a projected improvement of **206,147**. This traversal counts each shared dependency once. Some old automatically generated helpers drop out as well. Independent whole-proof certification of this mixed candidate is outstanding.

The exact-reuse lower bound for this archive is 2,369,214,350 nodes. It leaves at most 55,447 nodes of further improvement using the theorem-reference substitutions in that search. The six-term projection is 150,700 nodes below that bound. Its custom polynomial proofs use a different class of replacements.

## Reproduce the mixed-graph count

Download the [submission manifest](https://raw.githubusercontent.com/nikete/rh_golf/e40e3248dbce95e4b2a746f722293dee1de3b7df/candidates/optimized-2369269797.jsonl.gz) and use the pinned graph from RH Golf. With this directory as your working directory, run:

```sh
python3 measure.py --repo "$RH_GOLF" --graph "$RH_GOLF/.out/archive-graph" --portfolio "$MANIFEST"
```
