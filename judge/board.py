"""Trusted receipt aggregation and static pages. No API calls from the site."""
import argparse
from collections import defaultdict
from archive_portfolio import PORTFOLIO_VERIFIER
from fetch_graph import UPSTREAM, read_pin, release_tag
from impact import attach_measurements, footprint_size, provisional_project, score_project, validate_impact
from html import escape as esc
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlencode

from run import CONFIG, TARGETS, SEASON, ROOT, LOGIN, SOURCE_URL, import_origin, validate_score, event_submission, valid_target, open_graph

REPO_RE = re.compile(r"[a-zA-Z0-9-]+/[a-zA-Z0-9._-]+\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
REPO = os.getenv("GITHUB_REPOSITORY", "nikete/rh_golf")
if not REPO_RE.fullmatch(REPO):
    raise ValueError("Invalid repository")
GITHUB = "https://github.com/" + REPO
CHECKER_LABELS = {"comparator": "Comparator", "lean_kernel": "Lean kernel", "nanoda": "nanoda",
                  "con_leche": "con-leche", "con_leche_compare": "con-leche --compare"}


def target_key(hole):
    return {"Formalism.VW.rh_of_right": "reflection", "riemannHypothesis": "riemann"}.get(hole, hole)


def record_size(row):
    if target_key(row["hole"]) != "riemann":
        return row["nodes"]
    if row.get("standalone_rh_nodes") is not None:
        return row["standalone_rh_nodes"]
    if "impact" in row:
        return footprint_size(row["impact"])
    return None


def record_order(row):
    size = record_size(row)
    return size is None, size or 0, row["issue"]


def player_key(row):
    name = row["author"]
    return name if name.startswith("https://") else name.lower()


def chosen(rows):
    """One personal best per hole. Earlier issue breaks a personal tie without changing points."""
    best = {}
    for row in rows:
        key = (player_key(row), target_key(row["hole"]))
        if key not in best or record_order(row) < record_order(best[key]):
            best[key] = row
    return list(best.values())


VERIFICATION_LABELS = {"exact-reuse-delta": "Exact-reuse transformation", "full-export": "Full export audit",
                       "original-archive": "Original archive"}


def rank_targets(rows, refs, credits):
    pars = {hole: size for hole, r in refs.items() if (size := record_size(r)) is not None}
    hole_credits = defaultdict(int)
    for row in rows:
        hole_credits[player_key(row), target_key(row["hole"])] += credits.get(row["issue"], 0)
    players = {}
    holes = defaultdict(list)
    for r in sorted(chosen(rows), key=record_order):
        hole, who = target_key(r["hole"]), player_key(r)
        size = record_size(r)
        if size is not None:
            pars[hole] = min(pars.get(hole, size), size)
        points = hole_credits[who, hole]
        best = dict(r, points=points, entry_points=credits.get(r["issue"], 0))
        if hole == "riemann":
            best["complete_rh_nodes"] = size
        holes[hole].append(best)
        player = players.setdefault(who, {"author": r["author"], "holes": 0, "points": 0})
        player["holes"] += 1
        player["points"] += points
    leaders = sorted(players.values(), key=lambda p: (-p["points"], p["author"].lower()))
    return pars, holes, leaders


def standings(rows, refs, baseline, graph=None, *, audit_dir=None):
    """Official results concern complete RH routes with independent evidence."""
    project, credits = score_project(rows, refs, baseline, graph, audit_dir=audit_dir)
    covered = defaultdict(list)
    for audit in project["audits"]:
        for issue in audit["entries"]:
            covered[issue].append({k: audit[k] for k in ("verification_kind", "evidence_url", "route", "entries")})
    personal_evidence = defaultdict(list)
    player_evidence = defaultdict(list)
    by_issue = {r["issue"]: r for r in rows}
    for event in project["history"]:
        for issue, amount in event["credits"].items():
            if amount:
                row = by_issue[issue]
                evidence = {k: event[k] for k in ("verification_kind", "evidence_url")}
                award = {**evidence, "issue": issue, "points": amount}
                player_evidence[player_key(row)].append(award)
                personal_evidence[player_key(row), target_key(row["hole"])].append(award)
    certified = [dict(r, verification=covered[r["issue"]]) for r in rows if r["issue"] in covered]
    _, _, leaders = rank_targets(certified, {}, credits)
    for player in leaders:
        player["points_evidence"] = player_evidence[player_key(player)]
    singletons = {a["entries"][0] for a in project["audits"] if len(a["entries"]) == 1 and not a["course_reflection"]}
    roots = [r for r in certified if r["issue"] in singletons and target_key(r["hole"]) == "riemann"]
    _, root_bests, _ = rank_targets(roots, {}, credits)
    for hole, bests in root_bests.items():
        for r in bests:
            r["points_evidence"] = personal_evidence[player_key(r), hole]
            r["points"] = sum(a["points"] for a in r["points_evidence"])
    return {"riemann": project["current_nodes"]}, root_bests, leaders, project, credits


def provisional_standings(rows, refs, baseline, graph=None):
    project, credits = provisional_project(rows, refs, baseline, graph)
    return *rank_targets(rows, refs, credits), project, credits


def run_url(r):
    if r.get("run"):
        return f"{GITHUB}/actions/runs/{r['run']}/attempts/{r.get('attempt', 1)}"
    return GITHUB + "/tree/main/examples"


def validate_row(r):
    validate_score(r)
    if "impact" in r:
        validate_impact(r["impact"])
    if (r.get("status") != "accepted" or r.get("season") != SEASON or not valid_target(r["hole"])
            or not LOGIN.fullmatch(r["author"]) or not HEX.fullmatch(r["source_sha256"])
            or not HEX.fullmatch(r["certificate_sha256"])):
        raise ValueError("Invalid receipt")
    for k in ("issue", "run", "attempt"):
        if type(r[k]) is not int or r[k] <= 0:
            raise ValueError("Invalid GitHub identifier")


def record(event, receipt, folder):
    stamp = json.loads(receipt.read_text())
    if stamp["status"] != "accepted":
        raise ValueError("Cannot rank rejected entries")
    hole, src, who = event_submission(event)
    import hashlib
    if stamp["hole"] != hole or stamp["source_sha256"] != hashlib.sha256(src.encode()).hexdigest():
        raise ValueError("Receipt/source mismatch")
    row = {**stamp, "author": who, "issue": event["issue"]["number"],
           "run": int(os.environ["GITHUB_RUN_ID"]), "attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
           "commit": os.environ["GITHUB_SHA"], "submitted": event["issue"]["created_at"]}
    origin, _ = import_origin(event)
    if origin:
        row["source_url"] = origin
    validate_row(row)
    dest = folder / SEASON / str(row["issue"])
    dest.mkdir(parents=True, exist_ok=True)
    # Rerunning a workflow does not mint another score. Preserve the immutable source for inspection.
    if (dest / "score.json").exists():
        previous = json.loads((dest / "score.json").read_text())
        if any(previous[k] != row[k] for k in ("source_sha256", "nodes", "hole", "certificate_sha256")):
            raise ValueError("Non-reproducible rerun of an accepted entry")
        for key in ("archive_module", "archive_deps", "standalone_rh_nodes", "combine", "verifier", "axioms_scope",
                    "portfolio_coverage", "portfolio_url", "portfolio_sha256"):
            if previous.get(key) != row.get(key):
                raise ValueError("Non-reproducible archive substitution")
        if "impact" in row:
            supplement = dest / "impact.json"
            old = previous.get("impact")
            if supplement.exists():
                old = json.loads(supplement.read_text())["impact"]
            if old is not None and old != row["impact"]:
                raise ValueError("Non-reproducible whole-proof measurement")
            if old is None:
                supplement.write_text(json.dumps({k: row[k] for k in
                    ("hole", "source_sha256", "certificate_sha256", "impact")}, indent=2) + "\n")
        return
    (dest / "Entry.lean").write_text(src)
    (dest / "score.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")


def elem_table(cols, rows, empty):
    cells = "".join("<th scope='col'>" + c + "</th>" for c in cols)
    body = "".join("<tr>" + "".join("<td>" + c + "</td>" for c in row) + "</tr>" for row in rows)
    if not body:
        body = f"<tr><td colspan='{len(cols)}' class='empty'>{empty}</td></tr>"
    return f"<div class='scroll'><table><thead><tr>{cells}</tr></thead><tbody>{body}</tbody></table></div>"


def player(r):
    if r["author"].startswith("https://"):
        return link(r["author"], r["author"])
    name = esc(r["author"])
    return f"<a href='https://github.com/{name}'>@{name}</a>"


def ordinal(items, value):
    last = None
    for i, item in enumerate(items, 1):
        if item[value] != last:
            rank = i
            last = item[value]
        yield rank, item


def submit_url(h):
    args = {"title": f"[entry] {h}", "body": "```lean\n-- Replace this with your proof.\n"
            f"theorem Entry.answer : {TARGETS[h]} := by\n  sorry\n```"}
    return GITHUB + "/issues/new?" + urlencode(args)


def link(url, text):
    return f"<a href='{esc(url, quote=True)}'>{esc(text)}</a>"


def fmt(n):
    return f"{n:,}"


def historic_measurements():
    if REPO.lower() != UPSTREAM.lower():
        return {}
    return json.loads((ROOT / "judge/historic_impact.json").read_text())


def read_ledger_row(file, backfills):
    row = json.loads(file.read_text())
    supplement = file.with_name("impact.json")
    if supplement.exists():
        row, = attach_measurements([row], {str(row["issue"]): json.loads(supplement.read_text())})
    row, = attach_measurements([row], backfills)
    validate_row(row)
    if str(row["issue"]) != file.parent.name:
        raise ValueError("Ledger directory and issue number differ")
    if "source_url" in row:
        if not SOURCE_URL.fullmatch(row["source_url"]):
            raise ValueError("Invalid external finding URL")
        row = dict(row, submitted_by=row["author"], author=row["source_url"])
    return row


def render(ledger, output):
    backfills = historic_measurements()
    rows = [read_ledger_row(file, backfills) for file in sorted((ledger / SEASON).glob("*/score.json"))]
    refs = {r["hole"]: r for r in json.loads((ROOT / "judge/references.json").read_text())}
    baseline = json.loads((ROOT / "judge/baseline.json").read_text())
    graph = open_graph() if any("archive_deps" in row for row in rows) else None
    pars, holes, _, measured, estimates = provisional_standings(rows, refs, baseline, graph)
    audit_dir = ledger / SEASON / "audits"
    official_records, official_bests, leaders, project, credits = standings(rows, refs, baseline, graph, audit_dir=audit_dir)
    audits_for = defaultdict(list)
    transcript_links = {}
    for audit in project["audits"]:
        subject = audit["subject_id"]
        if "entrant_proof" in audit:
            issue, = audit["entries"]
            base = f"https://raw.githubusercontent.com/{REPO}/golf-scores/ledger/{SEASON}/{issue}"
            audit["entrant_proof_url"] = base + "/entrant-proof.json"
            audit["witness_url"] = base + "/entrant.rhproof.gz"
        if audit["verification_kind"] == "full-export":
            receipt = json.loads((audit_dir / f"{subject}.json").read_text())
            checkers = defaultdict(list)
            for checker, label in CHECKER_LABELS.items():
                checkers[receipt["checker_receipt"]["checks"][checker]["log_sha256"]].append(label)
            transcript_links[subject] = [
                link(f"https://raw.githubusercontent.com/{REPO}/golf-scores/ledger/{SEASON}/audits/logs/{digest}.log.gz",
                     " / ".join(names) + " log")
                for digest, names in checkers.items() if (audit_dir / "logs" / f"{digest}.log.gz").is_file()]
        for issue in audit["entries"]:
            audits_for[issue].append(audit)
    for r in rows:
        issue = r["issue"]
        r["points"] = credits.get(issue, 0)
        r["provisional_points"] = estimates.get(issue, 0)
        r["audit_status"] = "certified-route" if issue in audits_for else "pending"
        r["audit_subjects"] = sorted({a["subject_id"] for a in audits_for[issue]})
        r["verification"] = [{k: a[k] for k in ("verification_kind", "evidence_url", "route", "entries")}
                             for a in audits_for[issue]]
        r["points_evidence"] = [{"points": h["credits"][issue], "verification_kind": h["verification_kind"],
                                 "evidence_url": h["evidence_url"]} for h in project["history"] if h["credits"].get(issue)]
    output.mkdir(parents=True, exist_ok=True)
    for file in ("style.css", "identity.svg", "critical-strip.svg", "copy-prompt.js"):
        shutil.copyfile(ROOT / "site" / file, output / file)
    (output / ".nojekyll").write_text("")
    shell = (ROOT / "site/base.html").read_text()

    def page(path, title, body):
        (output / path).write_text(shell.replace("{{TITLE}}", esc(title)).replace("{{BODY}}", body)
                                  .replace("{{REPO}}", GITHUB))

    leaderboard = elem_table(["Rank", "Player", "Targets", "RH nodes saved", "Share of original RH"],
        [[str(rank), player(p), str(p["holes"]), f"<strong>{fmt(p['points'])}</strong>",
          f"{100*p['points']/project['archive_nodes']:.8f}%"]
         for rank, p in ordinal(leaders, "points")],
        "No player has a certified complete route yet.")
    entry_url = GITHUB + "/issues/new?template=entry.md"
    archive_url = "https://github.com/Deicyde/riemann-hypothesis/tree/40e56bab026552e089d7afcfeff08d2defb9c005/src"
    graph_url = f"https://github.com/{UPSTREAM}/releases/tag/{release_tag(read_pin())}"
    large_sources = archive_url.replace("/tree/", "/blob/") + "/Development/AbelianVarietyTheory/Proofs/IwasawaDecomposition"
    archive_names = {"reflection": "Formalism.VW.rh_of_right", "riemann": "riemannHypothesis"}
    target_names = {r["issue"]: archive_names.get(r["hole"], r["hole"]) for r in rows}
    for r in rows:
        target = target_names[r["issue"]]
        standalone = r.get("standalone_rh_nodes")
        if standalone is None and "impact" in r:
            size = r["impact"]["private_nodes"] + sum(r["impact"]["shared"].values())
            if target == "Formalism.VW.rh_of_right":
                standalone = baseline["spine_nodes"] + size
            elif target == "riemannHypothesis":
                standalone = size
        if r["hole"] == "window-logic":
            standalone = project["archive_nodes"]
        r["standalone_saved_nodes"] = None if standalone is None else project["archive_nodes"] - standalone

    featured = []
    for name, weight, source in (
            ("GlobalTheory.HeightCounting.SideCopy.LamCopy.lam_copy", 5_538_412, "LamCopy.lean#L15"),
            ("GlobalTheory.HeightCounting.SideCopy.sigSpan_copy", 4_598_434, "RingSpecNormalisedCharacterEq.lean#L97")):
        candidates = (r for r in rows if target_names[r["issue"]] == name)
        best = max(candidates, key=lambda r: (r["standalone_saved_nodes"] is not None,
                                              r["standalone_saved_nodes"] or 0, -r["issue"]), default=None)
        status = "Open"
        if best:
            issue, saved = best["issue"], best["standalone_saved_nodes"]
            label = f"#{issue}" if saved is None else f"#{issue} · {fmt(saved)} saved"
            status = link(f"{GITHUB}/issues/{issue}", label)
        featured.append([name, fmt(weight), status, link(f"{large_sources}/{source}", source.split("#")[0] + " ↗")])
    large_targets = elem_table(["Declaration", "Original local nodes", "Best provisional standalone entry", "Source"], featured, "")

    def standalone_cell(row):
        savings = row["standalone_saved_nodes"]
        if savings is not None:
            return fmt(savings)
        return "Needs partner" if row["hole"] in ("prime-window", "prime-supply") else "Pending"

    def evidence_links(row):
        issue = row["issue"]
        method = row.get("verifier")
        if method == PORTFOLIO_VERIFIER:
            from reuse.manifest import validate_url
            try:
                source = link(validate_url(row["portfolio_url"]), "Manifest (.jsonl.gz)")
            except ValueError:
                source = "Manifest unavailable"
            receipt = link(run_url(row), method)
        else:
            reuse = method == "pinned-export-exact-reuse-v1"
            source = link(f"proofs/{issue}.lean", "Instruction" if reuse else "Proof")
            receipt = link(run_url(row), "Export receipt" if reuse else "CI receipt")
        links = [source, receipt]
        for audit in audits_for[issue]:
            links.append(link(audit["evidence_url"], VERIFICATION_LABELS[audit["verification_kind"]]))
            links.append(link(run_url(audit), "Verification job"))
            if "entrant_proof" in audit:
                links.append(link(audit["entrant_proof_url"], "Entrant proof receipt"))
                links.append(link(audit["witness_url"], "Download witness"))
            if audit["verification_kind"] == "full-export":
                links.extend(transcript_links[audit["subject_id"]])
        return " · ".join(links)

    def accepted_entry(row):
        issue = row["issue"]
        name = target_names[issue]
        target = link("riemann.html", name) if name == "riemannHypothesis" else esc(name)
        local_size = fmt(row["nodes"])
        if row.get("verifier") == PORTFOLIO_VERIFIER:
            coverage = row["portfolio_coverage"]
            target += f"<br><small>{fmt(coverage['reachable'])} of {fmt(coverage['submitted'])} substitutions reachable</small>"
            local_size = "—"
        elif row.get("verifier") == "pinned-export-exact-reuse-v1":
            target += "<br><small>Reuses " + esc(row["reuse_donor"]) + "</small>"
        return [link(f"{GITHUB}/issues/{issue}", f"#{issue}"), target, player(row), local_size,
                standalone_cell(row), fmt(row["provisional_points"]), fmt(row["points"]),
                " / ".join(dict.fromkeys(VERIFICATION_LABELS[v["verification_kind"]]
                                         + (" (standalone)" if row.get("combine") and v["verification_kind"] == "exact-reuse-delta" else "")
                                         for v in row["verification"])) or "Pending", evidence_links(row)]

    entries_table = elem_table(["Entry", "Target", "Player", "Local nodes", "Estimated nodes saved alone", "Provisional points", "Certified points", "Verification", "Evidence"],
        [accepted_entry(r) for r in sorted(rows, key=lambda r: r["issue"], reverse=True)],
        "The first accepted replacement will appear here.")
    pct = 100 * project["saved_nodes"] / project["archive_nodes"]
    total_panel = f"""<section id='progress'><div class='sectionhead'><h2>Certified whole-proof progress</h2>
      {link(GITHUB + '/blob/main/judge/baseline.json', 'Baseline receipt ↗')} ·
      {link('rules.html#transformations', 'How certification works →')}</div>
      <div class='footprints'><div><small>Original ordinary RH</small><strong>{fmt(project['archive_nodes'])}</strong></div>
      <div><small>Certified complete proof</small><strong>{fmt(project['current_nodes'])}</strong></div>
      <div><small>Nodes removed</small><strong>{fmt(project['saved_nodes'])}</strong></div></div>
      <p>{pct:.8f}% of the original proof. The opening reference saved {fmt(project['course_saved_nodes'])} nodes.
      Players have contributed {fmt(project['community_saved_nodes'])} more.</p>
      <p>The best provisional measurement is <strong>{fmt(measured['current_nodes'])} nodes</strong>.
      Exact theorem substitutions can earn points through a transformation certificate. Custom and mixed proofs earn points after full-export verification.</p></section>"""
    accounts = {r["issue"]: (r["author"] if r["author"].startswith("https://") else "@" + r["author"]) for r in rows}
    changes = []
    for h in reversed(project["history"]):
        credit_links = [link(f"{GITHUB}/issues/{i}", f"{accounts[i]} · {fmt(amount)}")
                        for i, amount in h["credits"].items()]
        changes.append([link(f"{GITHUB}/issues/{h['issue']}", f"#{h['issue']}"),
                        esc(target_names[h["issue"]]), fmt(h["before_nodes"]), fmt(h["after_nodes"]), ", ".join(credit_links),
                        link(h["evidence_url"], VERIFICATION_LABELS[h["verification_kind"]])])
    bounty_rows = []
    project["bounties"] = []
    for issue, name, denominator, percent in (
            (3, "The Critical Cut", 1000, "0.1%"),
            (4, "The Riemann Razor", 100, "1%"),
            (5, "The Great Zeta Vanishing", 10, "10%")):
        required = (project["archive_nodes"] + denominator - 1) // denominator
        limit = project["archive_nodes"] - required
        first = next((event for event in project["history"] if event["after_nodes"] <= limit), None)
        winners = first["entries"] if first else ()
        evidence = {k: first[k] for k in ("verification_kind", "evidence_url")} if first else {}
        project["bounties"].append(dict(name=name, required_saved_nodes=required, winning_issues=winners, **evidence))
        status = ", ".join(link(f"{GITHUB}/issues/{i}", accounts[i]) for i in winners)
        bounty_rows.append([link(f"{GITHUB}/issues/{issue}", name), percent, fmt(required),
                            status or f"{fmt(project['current_nodes'] - limit)} nodes to go"])
    bounties = "<section id='bounties'><h2>Open proof bounties</h2><p>Earn a title for the first certified complete proof to cross each threshold. Winning partners share the title. All awards are recognition only.</p>" + elem_table(
        ["Title", "Cut", "Total nodes saved to qualify", "Progress"], bounty_rows, "") + "</section>"
    history_table = ""
    if changes:
        history_table = "<h3>Record improvements</h3>" + elem_table(
            ["Entry", "Target", "Before", "After", "Credit", "Verification"], changes, "")
    if project["pending_issues"]:
        history_table += "<p>Entries waiting for certification include " + ", ".join(
            link(f"{GITHUB}/issues/{i}", f"#{i}") for i in project["pending_issues"]) + ".</p>"
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## Start an agent\n", 1)[1].split("\n## ", 1)[0]
    prompt = section.split("```text\n", 1)[1].split("\n```", 1)[0]
    (output / "agent-prompt.txt").write_text(prompt + "\n")
    page("index.html", "RH Golf · Riemann proof league", f"""
    <section class='hero'><div class='herocopy'>
    <h1>Riemann<br><em>Proof Golf</em></h1><p class='intro'>We search the public web for shorter Lean proofs of the Riemann hypothesis. You can also submit a replacement directly. Every candidate goes through the same judge.</p>
    <div class='buttons'><a class='primary' href='{entry_url}'>Submit a replacement ↗</a>
    <a class='plain' href='#agent'>Play with an agent →</a></div></div>
    <figure><img src='critical-strip.svg' width='530' height='322' alt='The critical line at real part one half, with the first three positive zeta zero heights marked.'>
    <figcaption>Critical strip <span>ζ(s) = 0</span></figcaption></figure></section>
    <section id='verification'><h2>What counts as a shorter proof?</h2>
      <p>We look for improvements in papers, repositories, pull requests and other proof competitions. When we find public proof code that fits an archive declaration, we enter it and credit the URL of the original finding as the player. Ideas still awaiting code or missing hypotheses stay in the <a href='{GITHUB}/blob/main/docs/external-projects.md'>external project directory</a>.</p>
      <p>The judge checks that the replacement proves the same statement with the same assumptions. It measures the complete proof of ordinary RH by counting the Lean expression nodes it still needs above the fixed Lean and Mathlib libraries. Shared dependencies count once. Deleting a thousand lines can save zero nodes if the proof never used them.</p>
      <p>A checked theorem substitution can be certified against the verified archive. A custom proof first receives a local kernel check and a provisional measurement. Official credit requires certification of the complete result. Each node below the previous certified record earns one point. <a href='rules.html#validation'>What the judge checks →</a></p>
    </section>
    <section id='agent' class='agent-start'>
      <h2>Play with an agent</h2>
      <p>Paste this into a coding agent with a terminal. It will fetch the current record, try theorem substitutions and measure what they save. The starter needs Git, curl and Python 3.11+ on Linux or macOS.</p>
      <div class='buttons'><button type='button' id='copy-prompt' class='primary' hidden>Copy agent prompt</button>
      <a href='agent-prompt.txt'>Open plain text</a>
      <a href='{GITHUB}/blob/main/README.md#submit-your-agents-result'>Submission guide</a></div>
      <details id='agent-details'><summary>Read the prompt</summary><pre id='agent-prompt' tabindex='0'>{esc(prompt)}</pre></details>
      <span id='copy-status' role='status'></span><script src='copy-prompt.js' defer></script>
    </section>
    {total_panel}{bounties}<section id='course' class='submit-target'><div class='sectionhead'><h2>Choose a declaration</h2>
    <div>{link(archive_url, 'Browse the archive ↗')} · {link(graph_url, 'Declaration names and node costs ↗')}</div></div>
    <p>Use the declaration’s full Lean name in a new issue title. For example, to replace the reflection step, use</p>
    <pre>[entry] Formalism.VW.rh_of_right</pre>
    <p>Put your replacement, named <b>Entry.answer</b>, in a fenced Lean block in the issue body. A theorem must prove the original statement.
    To replace the entire proof, use <b>[entry] riemannHypothesis</b> and prove Mathlib’s <b>RiemannHypothesis</b>.</p>
    <p>Found an existing theorem with the exact same statement and universe parameters? Put one line in the Lean fence that names the donor.</p>
    <pre>reuse Fully.Qualified.Donor</pre>
    <p>The judge can certify this substitution against the original archive and award points for a smaller complete proof. <a href='rules.html#reuse'>Exact reuse rules →</a></p>
    <p>For a portfolio, target <b>riemannHypothesis</b> and use <b>reuse-file</b> with a pinned manifest. Generate a portable certificate on your own machine and submit the resulting <b>issue.md</b>. <a href='{GITHUB}/blob/main/docs/entrant-proof.md'>Generate an entry with evidence ↗</a> · <a href='rules.html#combinations'>Portfolio format →</a></p>
    <div class='buttons'><a class='primary' href='{entry_url}'>Open an entry ↗</a><a class='plain' href='rules.html'>Submission rules →</a></div></section>
    <section id='large-targets'><h2>Two large proofs to shrink</h2>
    <p>Ordinary RH uses both declarations. Each count measures the original declaration’s type and proof body.
    The points you earn depend on which dependencies your replacement still uses and how much it improves the current record.</p>{large_targets}
    <p>Copy a declaration name into your issue title after <b>[entry]</b>. These modules have large import trees. Building one from scratch can exceed the hosted runner’s time or memory limit. <a href='rules.html'>Entry limits →</a></p></section>
    <section id='standings'><div class='sectionhead'><h2>Certified leaderboard</h2><span>{len(leaders)} players</span></div>
    {leaderboard}{history_table}</section>
    <section id='entries'><div class='sectionhead'><h2>Submissions and verification</h2><span>{len(rows)} proofs</span></div><p>The evidence identifies how each entry was checked. A verified exact-reuse transformation or a verified full export can earn certified points. Provisional measurements stay available for comparison.</p>{entries_table}</section>""")
    for h in CONFIG:
        k = h["id"]
        size_key = "complete_rh_nodes" if k == "riemann" else "nodes"
        size_label = "Complete RH nodes" if k == "riemann" else "Local nodes"
        record_title = "Provisional complete proof measurements" if k == "riemann" else "Provisional local measurements"
        measured_entries = (r for r in holes[k] if r.get(size_key) is not None)
        ranks = [[str(rank), player(r), fmt(r[size_key]), str(r["points"]), evidence_links(r)]
                 for rank, r in ordinal(measured_entries, size_key)]
        standings_html = elem_table(["Rank", "Player", size_label, "Provisional points", "Evidence"], ranks, "No measured entries yet.")
        ref = refs.get(k)
        if ref:
            benchmark = f"""<div class='benchmark'><span>Course reference</span><strong>{fmt(ref['nodes'])} nodes</strong>
              {link(GITHUB + '/blob/main/' + h['example'], 'Read proof ↗')}</div>"""
        else:
            benchmark = "<div class='benchmark'><span>Course reference</span><strong>Open record</strong></div>"
        note = {
            "window-logic": "Practice target. Its local record is tracked. The ordinary RH proof has no dependency on this exercise.",
            "reflection": "The kernel checks the replacement at the archive’s reflection interface.",
            "prime-window": "This entry joins a proof of the estimate. The pair earns points when its complete RH proof sets a record.",
            "prime-supply": "This entry joins the criterion taking the estimate to RH. The pair can bypass the archive’s full nonvanishing argument.",
            "riemann": "A compact unconditional proof competes against the entire current RH proof."
        }[k]
        if k == "reflection" and measured.get("reflection_headroom_nodes") is not None:
            note += (f" Changing this step alone could save at most {fmt(measured['reflection_headroom_nodes'])} "
                     "more nodes against the current complete-proof record.")
        page(k + ".html", h["name"] + " · RH Golf", f"""
          <section class='inner'><a class='back' href='index.html#entries'>← Entries</a><p class='eyebrow'>{esc(h['class'])}</p>
          <h1>{esc(h['name'])}</h1><p class='intro'>{esc(h['description'])}</p><p>{esc(note)}</p>
          <code>theorem Entry.answer : {esc(h['target'])} := by …</code>
          <div class='buttons'><a class='primary' href='{esc(submit_url(k),quote=True)}'>Submit a proof ↗</a>
          <a class='plain' href='{GITHUB}/blob/main/League/Targets.lean'>Target definitions ↗</a></div>
          {benchmark}<div class='sectionhead'><h2>{record_title}</h2><span>Fewest nodes wins</span></div>{standings_html}</section>""")
    rules = (ROOT / "site/rules.html").read_text().replace("{{REPO}}", GITHUB)
    page("rules.html", "Scoring rules · RH Golf", rules)
    map_text = (ROOT / "site/proof.html").read_text()
    page("proof.html", "The proof map · RH Golf", map_text.replace("{{REFLECTION_NODES}}", fmt(baseline["reflection_nodes"]))
         .replace("{{ARCHIVE_NODES}}", fmt(baseline["archive_nodes"])))
    proofs = output / "proofs"
    proofs.mkdir(exist_ok=True)
    for r in rows:
        shutil.copyfile(ledger / SEASON / str(r["issue"]) / "Entry.lean", proofs / f"{r['issue']}.lean")
    for folder in ("audits", "deltas"):
        destination = output / folder
        destination.mkdir(exist_ok=True)
        verified = {Path(a["evidence_url"]).name for a in project["audits"] if Path(a["evidence_url"]).parent.name == folder}
        for stale in destination.glob("*.json"):
            if stale.name not in verified:
                stale.unlink()
        for name in sorted(verified):
            shutil.copyfile(ledger / SEASON / folder / name, destination / name)
    (output / "scores.json").write_text(json.dumps({"season": SEASON, "course_commit": os.getenv("COURSE_COMMIT"), "project": project,
        "holes": CONFIG, "references": refs,
        "records": official_records, "record_verification": {"riemann": {k: project[k] for k in ("verification_kind", "evidence_url")}},
        "personal_bests": dict(official_bests), "players": leaders,
        "provisional_project": measured, "provisional_records": pars, "provisional_personal_bests": dict(holes),
        "pending": project["pending_issues"], "accepted": rows}, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--site", type=Path)
    p.add_argument("--event", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    if args.event:
        record(json.loads(args.event.read_text()), args.receipt, args.ledger)
    if args.site:
        render(args.ledger, args.site)
