import unittest


class FailsTestCase(unittest.TestCase):
    def test_fails(self):
        self.assertTrue(False)
