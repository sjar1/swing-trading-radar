import unittest
import pandas as pd
from trading_radar import position, indicators, evaluate

class RadarTests(unittest.TestCase):
    def test_position_caps(self):
        x=position(10,9,5000)
        self.assertEqual(x["shares"],50)
        self.assertEqual(x["risk"],50)
        self.assertEqual(x["target_3r"],13)
    def test_invalid_stop(self):
        self.assertEqual(position(10,10)["shares"],0)
    def test_indicators(self):
        idx=pd.date_range("2025-01-01",periods=90,freq="B")
        close=pd.Series([10+i*.05 for i in range(90)],index=idx)
        df=pd.DataFrame({"Open":close,"High":close+.1,"Low":close-.1,"Close":close,"Volume":1000000},index=idx)
        out=indicators(df)
        self.assertEqual(len(out),90)
        self.assertTrue(pd.notna(out.iloc[-1].atr))
        self.assertIsNotNone(evaluate("TEST",df))
if __name__=="__main__":unittest.main()
