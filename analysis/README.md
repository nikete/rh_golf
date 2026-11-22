Warning: truncated output (original token count: 1079)
Total output lines: 49

# How much can exact theorem reuse save?

For the pinned RH Golf archive, every valid set of simultaneous exact theorem substitutions has at least **2,369,214,350** reachable expression nodes under the ordinary-RH scoring rule. The starting archive has 2,502,227,268. The maximum possible saving with these substitutions is therefore **133,012,918 nodes (5.31578%)**. The bound applies to every combination of eligible archive and Mathlib donors, including forward references that admit an acyclic order. New Lean proof terms and changes to definitions can open other possibilities.

## Reproduce

Extract the bundle, switch to its directory, and run the following with Python 3.11 or later. Only the graph download needs the network. The calculation itself uses the Python standard library.

```sh
git clone https://github.com/nikete/rh_golf.git rh_golf
git -C rh_golf checkout --detach c8e548a2da0d8ae62c9025645b29ecc01a00f075
python3 rh_golf/judge/fetch_graph.py --directory archive-graph
python3 -I -S bound.py --repo rh_golf --graph archive-graph
```

If GitHub’s public release download is unavailable, supply a locally reproduced graph bundle to the fetcher using `--bundle archive-graph.tar.gz`. The graph members still have to match the same pinned SHA-256 values. Expected output:

```json
{
  "baseline_nodes": 2502227268,
  "exact_reuse_lower_bound": 2369214350,
  "maximum_total_saving…379 tokens truncated…Its constraints have the form `A x <= b`, and `constant + c x` is a lower bound on the entry's true cost. For any nonnegative vector `y`, every feasible assignment costs at least

   `constant - b⋅y + Σⱼ min(0, cⱼ + (Aᵀy)ⱼ)`.

   The certificate supplies the integer numerators of `y` with common denominator 1024. The verifier reconstructs every coefficient and uses Python integer arithmetic. Rounding the resulting lower bound upward is valid because the tournament counts a whole number of nodes.

SciPy/HiGHS was used to find multipliers. Optional `--solve --certificate my-multipliers.gz` runs a new search and then verifies the result. A different dual can give a different valid lower bound. No optimizer is required to verify the supplied bound. The count is a bound relative to the tournament’s pinned graph, exact-signature index, and node metric. A legal entry attaining it has not been established.

## Data fingerprints

| Input | SHA-256 |
| --- | --- |
| Original compressed Lean export | `61a8938ad5f5e57397c1c0e3b954916af546d9004ade01c3555744a681b05381` |
| Archive graph lock file | `7af1330fda5dda55fd31f31a576c2af9f91043f061045e57ba98b5507b744714` |
| Expanded theorem-signature index | `4152f958a5a3e700075bd16e798db08d3ae67a597269fa43586cfcc93dc749b2` |
| Supplied compressed dual multipliers | `12c80b49ac220332c44fc9e537fa7fab53e7e55f652d8234761220b16ca11991` |
