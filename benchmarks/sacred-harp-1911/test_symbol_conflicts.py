import unittest
from types import SimpleNamespace

from symbol_conflicts import resolve_note_rest_conflicts


def make_rd(items):
    syms, tok = [], {}
    for i, (cls, p, box, staff, bar) in enumerate(items):
        syms.append(SimpleNamespace(i=i, box=box, staff=staff, bar=bar))
        tok[i] = {"cls": {"v": cls}, "real": {"p": p, "det": p, "ev": 0}}
    return SimpleNamespace(layout=SimpleNamespace(syms=syms), tok=tok)


class SymbolConflictTests(unittest.TestCase):
    def test_duplicate_note_rest_suppresses_weaker_and_audits(self):
        rd = make_rd([("note_quarter", .999, (10, 10, 30, 30), 0, 0),
                      ("rest_quarter", .68, (10, 10, 30, 30), 0, 0)])
        decisions = resolve_note_rest_conflicts(rd)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(rd.tok[0]["real"]["p"], .999)
        self.assertEqual(rd.tok[1]["real"]["p"], 0)
        self.assertEqual(rd.tok[1]["real"]["conflict_original_p"], .68)
        self.assertEqual(rd.tok[1]["real"]["conflict_reason"], "overlapping_note_rest")
        self.assertEqual((decisions[0]["winner_id"], decisions[0]["loser_id"]), (0, 1))

    def test_separated_low_margin_and_different_staff_bar_are_preserved(self):
        rd = make_rd([("note_quarter", .999, (0, 0, 20, 20), 0, 0),
                      ("rest_quarter", .7, (40, 0, 60, 20), 0, 0),
                      ("note_half", .7, (100, 0, 120, 20), 0, 0),
                      ("rest_half", .6, (100, 0, 120, 20), 0, 0),
                      ("note_eighth", .99, (150, 0, 170, 20), 0, 0),
                      ("rest_eighth", .6, (150, 0, 170, 20), 1, 0),
                      ("note_whole", .99, (200, 0, 220, 20), 0, 0),
                      ("rest_whole", .6, (200, 0, 220, 20), 0, 1)])
        self.assertEqual(resolve_note_rest_conflicts(rd), [])
        self.assertEqual([rd.tok[i]["real"]["p"] for i in range(8)],
                         [.999, .7, .7, .6, .99, .6, .99, .6])

    def test_chain_does_not_resurrect_suppressed_token(self):
        # A has highest probability, matches B and C; B must not suppress C after losing.
        rd = make_rd([("note_a", .99, (0, 0, 20, 20), 0, 0),
                      ("rest_b", .7, (3, 0, 23, 20), 0, 0),
                      ("note_c", .68, (6, 0, 26, 20), 0, 0)])
        decisions = resolve_note_rest_conflicts(rd, min_iou=.4)
        self.assertEqual([(d["winner_id"], d["loser_id"]) for d in decisions], [(0, 1)])
        self.assertEqual(rd.tok[1]["real"]["p"], 0)
        self.assertEqual(rd.tok[2]["real"]["p"], .68)


if __name__ == "__main__":
    unittest.main()
