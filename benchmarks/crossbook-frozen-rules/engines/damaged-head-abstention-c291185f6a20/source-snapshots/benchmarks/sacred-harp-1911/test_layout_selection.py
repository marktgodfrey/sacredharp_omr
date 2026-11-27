import unittest
from layout_selection import choose_layout


def xml(n):
    return '<score-partwise>' + ''.join(f'<part id="P{i}"/>' for i in range(n)) + '</score-partwise>'


class LayoutSelectionTests(unittest.TestCase):
    def test_cleanup_must_repair_structure_and_three_parts_are_supported(self):
        picked, _ = choose_layout([('raw', {'staves': 4, 'systems': 4}, xml(1)),
                                   ('clean', {'staves': 4, 'systems': 1}, xml(4))])
        self.assertEqual(picked, 'clean')
        picked, _ = choose_layout([('raw', {'staves': 6, 'systems': 2}, xml(3)),
                                   ('clean', {'staves': 6, 'systems': 1}, xml(6))])
        self.assertEqual(picked, 'raw')

    def test_equal_valid_structures_preserve_raw(self):
        picked, _ = choose_layout([('raw', {'staves': 8, 'systems': 2}, xml(4)),
                                   ('clean', {'staves': 8, 'systems': 2}, xml(4))])
        self.assertEqual(picked, 'raw')

    def test_both_broken_preserve_raw_even_if_cleanup_has_lower_penalty(self):
        picked, scores = choose_layout([('raw', {'staves': 8, 'systems': 1}, xml(8)),
                                        ('clean', {'staves': 8, 'systems': 6}, xml(3))])
        self.assertLess(scores[1]['penalty'], scores[0]['penalty'])
        self.assertEqual(picked, 'raw')


if __name__ == '__main__':
    unittest.main()
