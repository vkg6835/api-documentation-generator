import copy
import unittest

from app.quality import output_digest, quality_report


class QualityTests(unittest.TestCase):
    def setUp(self):
        accepted={"accepted":True,"output":{"behavior":"Returns an item."}}
        rejected={"accepted":False,"error":"Invalid JSON"}
        self.capture={"model":"fixture","rubric":{},"cases":[{"id":"item","project":"inventory","method":"GET","path":"/items","essential_facts":["Returns an item."],"generations":{"source only":accepted,"source + usage":rejected}}]}
        self.review={"reviewer":"Test reviewer","method":"Source-based review","cases":{"item":{
            "source only":{"output_sha256":output_digest(accepted),"scores":{"correctness":2,"completeness":1,"clarity":2},"notes":"One fact is omitted.","unsupported_claims":[]},
            "source + usage":{"output_sha256":output_digest(rejected),"scores":None,"notes":"No accepted prose.","unsupported_claims":[]}}}}
        self.review["capture_sha256"]=output_digest(self.capture)

    def test_rejected_generations_are_reported_without_prose_scores(self):
        result=quality_report(self.capture,self.review)
        self.assertEqual(result["settings"]["source only"]["correctness"],2)
        self.assertEqual(result["settings"]["source + usage"]["accepted"],0)
        self.assertIsNone(result["settings"]["source + usage"]["correctness"])

    def test_changed_outputs_cannot_reuse_old_reviews(self):
        changed=copy.deepcopy(self.capture)
        changed["cases"][0]["generations"]["source only"]["output"]["behavior"]="Deletes an item."
        with self.assertRaisesRegex(ValueError,"outputs changed"):
            quality_report(changed,self.review)

    def test_all_cases_must_be_reviewed(self):
        self.review["cases"]={}
        with self.assertRaisesRegex(ValueError,"every captured case"):
            quality_report(self.capture,self.review)
