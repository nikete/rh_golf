# Submit a proof from your own machine

Use this path for an exact theorem substitution (`reuse`) or a complete list of substitutions (`reuse-file`). You can find the improvement, generate its witness and verify the final RH size on the same laptop or server. Anyone can check the resulting bytes. The judge needs the small audited indexes, Python 3.11+ and the submitted data. It runs on a standard GitHub runner.

## Copy into your agent

```text
Work in a current checkout of https://github.com/nikete/rh_golf on this machine.
Read the live certified size at https://nikete.github.io/rh_golf/scores.json (project.current_nodes).
Find an improvement using exact theorem reuse. Put the single reuse or reuse-file instruction in Entry.lean and set TARGET to the archive declaration, or riemannHypothesis for a portfolio.
Run python3 judge/entrant_proof.py make --target "$TARGET" --source Entry.lean --output submission
The command generates the witness and checks it locally. Compare the verified whole-RH node count with the live record. On success, return submission/title.txt and submission/issue.md. If authorized to enter, use their contents as the exact GitHub issue title and body, then report the judge verdict and official marginal points.
```

For an authorized entry, this submits both fences exactly as generated:

```sh
gh issue create --repo nikete/rh_golf --title "$(cat submission/title.txt)" --body-file submission/issue.md
```

## Replay the existing record locally

This worked example reproduces entry [#17](https://github.com/nikete/rh_golf/issues/17). It saves 119,634,132 nodes from the original 2,502,227,268. A new record must improve the live certified size to earn additional points.

```sh
git clone https://github.com/nikete/rh_golf.git
cd rh_golf
cat > Entry.lean <<'ENTRY'
reuse-file https://raw.githubusercontent.com/nikete/rh_golf/984b783cefabd615a7d833c7a04d0e7184e2e71e/candidates/earlier-theorems.jsonl.gz b21a998d186e8d4417d4fa4cdf5554fcb77076f5dbd445507136c5ca358d4ab7
ENTRY
python3 judge/entrant_proof.py make --target riemannHypothesis --source Entry.lean --output submission
```

Expected whole proof size **2,382,593,136 nodes**. The witness for the 203,183 substitutions occupies 18,514 compressed bytes. The generated issue body includes the witness inline. To verify the saved package independently:

```sh
python3 judge/entrant_proof.py verify --target riemannHypothesis \
  --source submission/Entry.lean --proof submission/entrant-proof.json
```

You can also check the [package generated on the entrant’s Mac](examples/17/entrant-proof.json) directly from this checkout:

```sh
python3 judge/entrant_proof.py verify --target riemannHypothesis \
  --source docs/examples/17/Entry.lean --proof docs/examples/17/entrant-proof.json
```

Both commands accept `--manifest PATH` for a local copy of the exact compressed portfolio and `--graph DIR` for the four audited graph files. With both inputs present and an inline or locally supplied witness, generation and verification work offline. The default graph directory is `.out/archive-graph`. Its first use fetches a public release and checks its hashes.

## What the witness proves

The original export fixes the RH statement, theorem types and admitted axioms. Each edit replaces a theorem body with a reference to an existing theorem of exactly the same exported type and ordered universe parameters. The original archive audit also checks the boundary with Lean and Mathlib, including library declarations whose proofs are omitted from the scoring graph.

The entrant supplies an ordering of the changed graph (encoded as corrections to the original ranks) and a bitset naming every declaration reachable from RH. The receiver binds these to the actual substitutions and pinned indexes, validates strict rank descent on every dependency edge, checks exact reachability and sums the audited weights. This checks the mathematical claim directly. It requires no trust in the entrant's machine, signing key, log or reported score. The points ledger keeps the submitted package, its binary witness and the verifier's result.

New Lean arguments, new helper lemmas and combinations with custom proofs use the Lean submission and full candidate-audit path. A `-- combine:` nomination on a single reuse entry can receive this certificate for its standalone size. A combined record requires evidence for the entire combination.

## If your witness exceeds the issue limit

The generator still saves and verifies `submission/entrant.rhproof.gz` locally. Publish this file in a public GitHub repository. Copy the raw file URL with the full commit SHA in the path, then build a short issue body using those exact bytes:

```sh
python3 judge/entrant_proof.py link --output submission --witness-url "$PINNED_RAW_GITHUB_URL"
```

The receiver checks the compressed SHA-256 and retains its own copy. To check such a package offline, add `--witness submission/entrant.rhproof.gz` to the verify command. The witness size limit is 32 MiB compressed.
