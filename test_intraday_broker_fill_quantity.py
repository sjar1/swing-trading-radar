import unittest
from intraday_broker_fill_quantity import compare
from intraday_persistent_recovery_simulator import PersistenceBlocked
class FillQuantityTests(unittest.TestCase):
    def check(self,saved,broker,phase="partially_filled"):
        return compare(persisted_quantity=saved,broker_order={"filled_qty":broker},phase=phase)
    def test_decimal_equivalence(self):
        x=self.check("0.50","0.500")
        self.assertTrue(x["quantity_equal"])
        self.assertFalse(x["execution_enabled"])
    def test_broker_greater(self):
        with self.assertRaises(PersistenceBlocked):self.check("0.5","0.75")
    def test_broker_less(self):
        with self.assertRaises(PersistenceBlocked):self.check("0.5","0.25")
    def test_negative(self):
        with self.assertRaises(PersistenceBlocked):self.check("0","-1")
    def test_nan(self):
        with self.assertRaises(PersistenceBlocked):self.check("0","NaN")
    def test_infinity(self):
        with self.assertRaises(PersistenceBlocked):self.check("0","Infinity")
    def test_missing(self):
        with self.assertRaises(PersistenceBlocked):self.check("0",None)
    def test_boolean(self):
        with self.assertRaises(PersistenceBlocked):self.check("0",False)
    def test_filled_zero(self):
        with self.assertRaises(PersistenceBlocked):self.check("0","0","filled")
    def test_ack_with_fill(self):
        with self.assertRaises(PersistenceBlocked):self.check("1","1","acknowledged")
if __name__=="__main__":unittest.main()
