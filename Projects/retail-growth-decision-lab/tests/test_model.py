import unittest
import pandas as pd
from pipeline.model import build_features, scenario


class TemporalIntegrityTests(unittest.TestCase):
    def test_future_orders_do_not_change_features(self):
        rows = [("1","a","2011-10-15",100.),("1","b","2011-11-01",50.),
                ("2","c","2011-12-01",999.),("1","d","2011-12-01",999.)]
        orders = pd.DataFrame(rows,columns=["customer_id","invoice_no","invoice_date","revenue"])
        orders["country"]="United Kingdom"
        orders["invoice_date"]=pd.to_datetime(orders.invoice_date)
        got=build_features(orders,"2011-11-01")
        self.assertEqual(list(got.customer_id),["1"])
        self.assertEqual(got.iloc[0].orders_90d,1)
        self.assertEqual(got.iloc[0].spend_90d,100.)
        self.assertEqual(got.iloc[0].purchased,1)
        shortened=build_features(orders.iloc[[0]],"2011-11-01")
        self.assertEqual(shortened.iloc[0].purchased,0)
        pd.testing.assert_frame_equal(got.drop(columns="purchased"),shortened.drop(columns="purchased"))

    def test_label_end_is_exclusive(self):
        orders=pd.DataFrame({"customer_id":["1","1"],"invoice_no":["a","b"],
            "invoice_date":pd.to_datetime(["2011-10-15","2011-12-01"]),"revenue":[100.,50.],"country":["UK","UK"]})
        self.assertEqual(build_features(orders,"2011-11-01").iloc[0].purchased,0)

    def test_zero_uplift_loses_contact_cost_and_budget_is_respected(self):
        frame=pd.DataFrame({"customer_id":["1","2"],"priority_score":[9.,8.],"purchase_probability":[.1,.2],"order_value":[100.,100.]})
        got=scenario(frame,budget=1.9,cost=1.,uplift=0.)
        self.assertEqual(got["selected_customers"],1)
        self.assertEqual(got["assumed_incremental_contribution"],-1.)
        self.assertEqual(scenario(frame,budget=0)["selected_customers"],0)

    def test_uplift_cannot_exceed_probability_headroom(self):
        frame=pd.DataFrame({"customer_id":["1"],"priority_score":[1.],"purchase_probability":[.99],"order_value":[100.]})
        got=scenario(frame,budget=1.,cost=1.,margin=1.,uplift=.5)
        self.assertAlmostEqual(got["assumed_incremental_orders"],.01)


if __name__=="__main__":
    unittest.main()
