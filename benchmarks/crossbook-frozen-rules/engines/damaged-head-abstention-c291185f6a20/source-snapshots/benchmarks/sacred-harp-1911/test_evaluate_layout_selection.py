import unittest
from evaluate_layout_selection import aggregate_rows


class AggregateTests(unittest.TestCase):
    def test_each_arm_uses_its_own_note_count_denominator(self):
        def arm(edits, denominator):
            return {'pitch_duration_edit_distance': edits, 'denominator': denominator,
                    'pitch_edit_distance': edits, 'pitch_denominator': denominator,
                    'layout_matches_expected_counts': True}
        result = aggregate_rows([{'default': arm(20, 100), 'selected': arm(10, 50),
                                  'switched': True, 'comparison': 'equal'}])
        self.assertEqual(result['default_pooled_error_rate'], .2)
        self.assertEqual(result['selected_pooled_error_rate'], .2)
        self.assertEqual(result['selected_pitch_pooled_error_rate'], .2)
        self.assertEqual(result['selected_pooled_denominator'], 50)


if __name__ == '__main__':
    unittest.main()
