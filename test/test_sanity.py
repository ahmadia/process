from twisted.trial import unittest

class SanityTestCase(unittest.TestCase):
    def test_sanity(self):
        a = 3
        b = 4
        self.assertEquals(a+b, 7)
#    def test_insanity(self):
#        a = 1
#        b = 1
#        self.assertEquals(a+b, 3)
