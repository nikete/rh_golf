"""Trusted receipt aggregation and static pages. No API calls from the site."""
import argparse
from collections import defaultdict
from impact import attach_measurements, score_project, validate_impact
from html import escape as esc
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlencode

from run import CONFIG, TARGETS, SEASON, ROOT, LOGIN, validate_score, event_submission

REPO_RE = re.compile(r"[a-zA-Z0-9-]+/[a-zA-Z0-9._-]+\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
REPO = os.getenv("GITHUB_REPOSITORY", "nikete/rh_golf")
if not REPO_RE.fullmatch(REPO):
    raise ValueError("Invalid repository")
GITHUB = "https://github.com/" + REPO


def chosen(rows):
    """One personal best per hole. Earlier issue breaks a personal tie without changing points."""
    best = {}
    for row in rows:
        key = (row["author"].lower(), row["hole"])
        if key not in best or (row["nodes"], row["issue"]) < (best[key]["nodes"], best[key]["issue"]):
            best[key] = row
    return list(best.values())


def standings(rows, refs, baseline):
    project, credits = score_project(rows, refs, baseline)
    pars = {hole: r["nodes"] for hole, r in refs.items()}
    hole_credits = defaultdict(int)
    for row in rows:
        hole_credits[row["author"].lower(), row["hole"]] += credits.get(row["issue"], 0)
    players = {}
    holes = defaultdict(list)
    for r in sorted(chosen(rows), key=lambda x: (x["nodes"], x["issue"])):
        hole, who = r["hole"], r["author"].lower()
        pars[hole] = min(pars.get(hole, r["nodes"]), r["nodes"])
        points = hole_credits[who, hole]
        holes[hole].append(dict(r, points=points, entry_points=credits.get(r["issue"], 0)))
        player = players.setdefault(who, {"author": r["author"], "holes": 0, "points": 0})
        player["holes"] += 1
        player["points"] += points
    leaders = sorted(players.values(), key=lambda p: (-p["points"], p["author"].lower()))
    return pars, holes, leaders, project, credits


def run_url(r):
    if r.get("run"):
        return f"{GITHUB}/actions/runs/{r['run']}/attempts/{r.get('attempt', 1)}"
    return GITHUB + "/tree/main/examples"


def validate_row(r):
    validate_score(r)
    if "impact" in r:
        validate_impact(r["impact"])
    if (r.get("status") != "accepted" or r.get("season") != SEASON or r["hole"] not in TARGETS
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
    validate_row(row)
    dest = folder / SEASON / str(row["issue"])
    dest.mkdir(parents=True, exist_ok=True)
    # Rerunning a workflow does not mint another score. Preserve the immutable source for inspection.
    if (dest / "score.json").exists():
        previous = json.loads((dest / "score.json").read_text())
        if any(previous[k] != row[k] for k in ("source_sha256", "nodes", "hole", "certificate_sha256")):
            raise ValueError("Non-reproducible rerun of an accepted entry")
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


def render(ledger, output):
    rows = []
    for file in sorted((ledger / SEASON).glob("*/score.json")):
        r = json.loads(file.read_text())
        supplement = file.with_name("impact.json")
        if supplement.exists():
            r, = attach_measurements([r], {str(r["issue"]): json.loads(supplement.read_text())})
        validate_row(r)
        rows.append(r)
    refs = {r["hole"]: r for r in json.loads((ROOT / "judge/references.json").read_text())}
    baseline = json.loads((ROOT / "judge/baseline.json").read_text())
    backfills = json.loads((ROOT / "judge/historic_impact.json").read_text())
    if REPO.lower() == "nikete/rh_golf":
        rows = attach_measurements(rows, backfills)
    pars, holes, leaders, project, credits = standings(rows, refs, baseline)
    for r in rows:
        r["points"] = credits.get(r["issue"], 0)
    output.mkdir(parents=True, exist_ok=True)
    for file in ("style.css", "identity.svg", "critical-strip.svg"):
        shutil.copyfile(ROOT / "site" / file, output / file)
    (output / ".nojekyll").write_text("")
    shell = (ROOT / "site/base.html").read_text()

    def page(path, title, body):
        (output / path).write_text(shell.replace("{{TITLE}}", esc(title)).replace("{{BODY}}", body)
                                  .replace("{{REPO}}", GITHUB))

    leaderboard = elem_table(["Rank", "Player", "Holes", "RH nodes saved", "Share of original RH"],
        [[str(rank), player(p), str(p["holes"]), f"<strong>{fmt(p['points'])}</strong>",
          f"{100*p['points']/project['archive_nodes']:.8f}%"]
         for rank, p in ordinal(leaders, "points")],
        "The first accepted entry opens the standings. Course references earn no player points.")
    cards = []
    for n, h in enumerate(CONFIG, 1):
        k = h["id"]
        size = f"{fmt(pars[k])} nodes" if k in pars else "Open record"
        entrants = len(holes[k])
        cards.append(f"""<a class='hole' href='{k}.html'><div class='holemeta'><span>Hole {n:02d}</span>
          <span>{esc(h['class'])}</span></div><h3>{esc(h['name'])}</h3>
          <p>{esc(h['description'])}</p><div class='holefoot'><b>{size}</b>
          <span>{entrants} player{'s' if entrants != 1 else ''} <i>↗</i></span></div></a>""")
    earn = sum(len(holes[h["id"]]) for h in CONFIG)
    pct = 100 * project["saved_nodes"] / project["archive_nodes"]
    total_panel = f"""<section id='progress'><div class='sectionhead'><h2>Whole-proof progress</h2>
      {link(GITHUB + '/blob/main/judge/baseline.json', 'Baseline receipt ↗')}</div>
      <div class='footprints'><div><small>Original ordinary RH</small><strong>{fmt(project['archive_nodes'])}</strong></div>
      <div><small>Current complete proof</small><strong>{fmt(project['current_nodes'])}</strong></div>
      <div><small>Nodes removed</small><strong>{fmt(project['saved_nodes'])}</strong></div></div>
      <p>{pct:.8f}% of the original proof. The opening reference saved {fmt(project['course_saved_nodes'])} nodes.
      Players have contributed {fmt(project['community_saved_nodes'])} more.</p></section>"""
    accounts = {r["issue"]: r["author"] for r in rows}
    changes = []
    for h in reversed(project["history"]):
        credit_links = [link(f"{GITHUB}/issues/{i}", f"@{accounts[i]} · {fmt(amount)}")
                        for i, amount in h["credits"].items()]
        changes.append([link(f"{GITHUB}/issues/{h['issue']}", f"#{h['issue']}"),
                        fmt(h["before_nodes"]), fmt(h["after_nodes"]), ", ".join(credit_links)])
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
        project["bounties"].append(dict(name=name, required_saved_nodes=required, winning_issues=winners))
        status = ", ".join(link(f"{GITHUB}/issues/{i}", "@" + accounts[i]) for i in winners)
        bounty_rows.append([link(f"{GITHUB}/issues/{issue}", name), percent, fmt(required),
                            status or f"{fmt(project['current_nodes'] - limit)} nodes to go"])
    bounties = "<section id='bounties'><h2>Open proof bounties</h2><p>Earn a title for the first complete proof to cross each threshold. Winning partners share the title. All awards are recognition only.</p>" + elem_table(
        ["Title", "Cut", "Total nodes saved to qualify", "Progress"], bounty_rows, "") + "</section>"
    history_table = ""
    if changes:
        history_table = "<h3>Record improvements</h3>" + elem_table(
            ["Entry", "Before", "After", "Credit"], changes, "")
    if project["pending_issues"]:
        history_table += "<p>Awaiting whole-proof replay: " + ", ".join(
            link(f"{GITHUB}/issues/{i}", f"#{i}") for i in project["pending_issues"]) + ".</p>"
    page("index.html", "RH Golf · Riemann proof league", f"""
    <section class='hero'><div class='herocopy'><p class='eyebrow'><span class='dot'></span> Season 01 · Open course</p>
    <h1>Riemann<br><em>Proof Golf</em></h1><p class='intro'>Find a smaller Lean proof of the Riemann hypothesis. Each point is one node removed from the best complete proof.</p>
    <div class='buttons'><a class='primary' href='#course'>Choose a hole <span>↓</span></a>
    <a class='plain' href='rules.html'>Scoring rules →</a></div></div>
    <figure><img src='critical-strip.svg' width='530' height='322' alt='The critical line at real part one half, with the first three positive zeta zero heights marked.'>
    <figcaption>Critical strip <span>ζ(s) = 0</span></figcaption></figure></section>
    {total_panel}{bounties}<section id='course'><div class='sectionhead'><h2>The course</h2><a href='proof.html'>How the holes fit together →</a></div><div class='holes'>{"".join(cards)}</div></section>
    <section id='standings'><div class='sectionhead'><h2>Leaderboard</h2><span>{len(leaders)} players · {earn} personal bests</span></div>
    {leaderboard}{history_table}</section>""")
    for i, h in enumerate(CONFIG, 1):
        k = h["id"]
        ranks = [[str(rank), player(r), fmt(r["nodes"]), str(r["points"]),
                  link(run_url(r), "CI receipt ↗") + " · " + link(f"proofs/{r['issue']}.lean", "Proof")]
                 for rank, r in ordinal(holes[k], "nodes")]
        standings_html = elem_table(["Local rank", "Player", "Local nodes", "RH nodes credited", "Evidence"], ranks, "This hole is open for its first entry.")
        ref = refs.get(k)
        if ref:
            benchmark = f"""<div class='benchmark'><span>Course reference</span><strong>{fmt(ref['nodes'])} nodes</strong>
              {link(GITHUB + '/blob/main/' + h['example'], 'Read proof ↗')}</div>"""
        else:
            benchmark = "<div class='benchmark'><span>Course reference</span><strong>Open record</strong></div>"
        note = {
            "window-logic": "Practice hole. Its local record is tracked. The ordinary RH proof has no dependency on this exercise.",
            "reflection": ("The kernel checks the replacement at the archive’s reflection interface. "
                           f"Changing this step alone could save at most {fmt(project['reflection_headroom_nodes'])} "
                           "more nodes against today’s complete-proof record."),
            "prime-window": "This entry joins a proof of the estimate. The pair earns points when its complete RH proof sets a record.",
            "prime-supply": "This entry joins the criterion taking the estimate to RH. The pair can bypass the archive’s full nonvanishing argument.",
            "riemann": "A compact unconditional proof competes against the entire current RH proof."
        }[k]
        page(k + ".html", h["name"] + " · RH Golf", f"""
          <section class='inner'><a class='back' href='index.html#course'>← Course</a><p class='eyebrow'>Hole {i:02d} · {esc(h['class'])}</p>
          <h1>{esc(h['name'])}</h1><p class='intro'>{esc(h['description'])}</p><p>{esc(note)}</p>
          <code>theorem Entry.answer : {esc(h['target'])} := by …</code>
          <div class='buttons'><a class='primary' href='{esc(submit_url(k),quote=True)}'>Submit a proof ↗</a>
          <a class='plain' href='{GITHUB}/blob/main/League/Targets.lean'>Target definitions ↗</a></div>
          {benchmark}<div class='sectionhead'><h2>Hole standings</h2><span>Fewest nodes wins</span></div>{standings_html}</section>""")
    rules = (ROOT / "site/rules.html").read_text().replace("{{REPO}}", GITHUB)
    page("rules.html", "Scoring rules · RH Golf", rules)
    map_text = (ROOT / "site/proof.html").read_text()
    page("proof.html", "The proof map · RH Golf", map_text.replace("{{REFLECTION_NODES}}", fmt(baseline["reflection_nodes"]))
         .replace("{{ARCHIVE_NODES}}", fmt(baseline["archive_nodes"])))
    proofs = output / "proofs"
    proofs.mkdir(exist_ok=True)
    for r in rows:
        shutil.copyfile(ledger / SEASON / str(r["issue"]) / "Entry.lean", proofs / f"{r['issue']}.lean")
    (output / "scores.json").write_text(json.dumps({"season": SEASON, "course_commit": os.getenv("COURSE_COMMIT"), "project": project,
        "holes": CONFIG, "references": refs,
        "records": pars, "players": leaders, "personal_bests": dict(holes), "accepted": rows}, indent=2) + "\n")


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
