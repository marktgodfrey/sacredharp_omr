import unittest
import numpy as np
from experiment_reader import PinnedInputs


class PinnedInputTests(unittest.TestCase):
    def test_reuses_owned_buffers_by_shape_without_changing_values(self):
        class FakeModel:
            def predict(self, inputs):
                self.last = inputs
                return {'result': inputs['image'].copy()}
        model = FakeModel()
        pinned = PinnedInputs(model)
        a = np.arange(6, dtype=np.float32).reshape(2, 3)
        np.testing.assert_array_equal(pinned.predict({'image': a})['result'], a)
        first = model.last['image']
        self.assertFalse(np.shares_memory(first, a))
        b = np.ones((2, 3), np.float32)
        np.testing.assert_array_equal(pinned.predict({'image': b})['result'], b)
        self.assertIs(model.last['image'], first)
        c = np.ones((3, 2), np.float32)
        pinned.predict({'image': c})
        self.assertIsNot(model.last['image'], first)
        self.assertTrue(any(value is first for value in pinned.buffers.values()))


if __name__ == '__main__':
    unittest.main()
