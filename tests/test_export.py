"""The audit follows kernel references and treats an inductive block as one declaration."""
from array import array
from contextlib import redirect_stdout
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge" / "baseline"))
from catalog import catalog, ROOTS


class ExportCatalogTests(unittest.TestCase):
    def test_elaboration_alias_is_free_and_inductive_rules_are_roots(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            with gzip.open(work / "mathlib-names.jsonl.gz", "wt") as names:
                names.write('["Nat"]\n')
            records = []
            names = {(): 0}

            def name(s):
                prefix = ()
                for part in s.split("."):
                    key = (*prefix, part)
                    if key not in names:
                        index = len(names)
                        records.append({"in": index, "str": {"pre": names[prefix], "str": part}})
                        names[key] = index
                    prefix = key
                return names[prefix]

            # Some real theorem records carry an unexported elaboration alias in "all".
            # The reference exporter walks the type and value, leaving that alias undefined.
            ignored = name("ElaboratedAlias")
            records.append({"axiom": {"name": name("Nat"), "type": 10}})
            for i, root in enumerate(ROOTS):
                records.append({"thm": {"name": name(root), "type": 10, "value": 20+i, "all": [ignored]}})
            records.append({"inductive": {
                "types": [{"name": name("Box"), "type": 8}],
                "ctors": [{"name": name("Box.mk"), "type": 9}],
                "recs": [{"name": name("Box.rec"), "type": 10, "rules": [{"rhs": 11}]}]}})
            (work / "declarations.ndjson").write_text("".join(json.dumps(r)+"\n" for r in records))
            with redirect_stdout(io.StringIO()):
                catalog(work)
            groups = array("I")
            groups.frombytes((work / "groups.bin").read_bytes())
            self.assertEqual(list(groups), [n for i in range(5) for n in (2, 10, 20+i)] + [4, 8, 9, 10, 11])
            owner = array("I")
            owner.frombytes((work / "owner.bin").read_bytes())
            self.assertEqual(owner[names[("Nat",)]], 0)
            self.assertEqual(owner[names[("Box",)]], owner[names[("Box", "mk")]])
