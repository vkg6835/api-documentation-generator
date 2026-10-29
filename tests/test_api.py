import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import storage, llm
from app.engine import analyze
from app.server import Handler, demo


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=storage.DB_PATH
        cls.temp=tempfile.TemporaryDirectory()
        storage.DB_PATH=Path(cls.temp.name)/"projects.sqlite3"
        storage.initialize()
        sample=demo("bookstore")
        cls.sample=sample
        cls.record=storage.insert(analyze(sample["files"],sample["name"]))
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.url=f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)
        storage.DB_PATH=cls.original
        cls.temp.cleanup()

    def request(self,path,body=None,origin=None):
        headers={"Content-Type":"application/json"}
        if origin:headers["Origin"]=origin
        request=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=5) as response:return response.status,json.load(response),response.headers
        except urllib.error.HTTPError as response:return response.code,json.load(response),response.headers

    def test_analyze_and_export_contract(self):
        code,record,_=self.request('/api/analyze',self.sample)
        self.assertEqual(code,201)
        code,spec,headers=self.request('/api/projects/'+record['id']+'/openapi')
        self.assertEqual(code,200)
        self.assertEqual(spec['openapi'],'3.1.0')
        self.assertIn('201',spec['paths']['/v1/books']['post']['responses'])
        self.assertIn('attachment',headers['Content-Disposition'])

    def test_source_name_validation(self):
        code,body,_=self.request('/api/analyze',{'files':[{'path':'../../outside.py','content':'x=1'}]})
        self.assertEqual(code,400)
        self.assertIn('relative',body['error'])

    def test_cross_origin_post_rejected(self):
        code,_,_=self.request('/api/analyze',self.sample,'http://example.invalid')
        self.assertEqual(code,403)

    def test_unknown_record_and_endpoint_are_rejected(self):
        self.assertEqual(self.request('/api/projects/DOC-9999')[0],404)
        code,body,_=self.request('/api/projects/'+self.record['id']+'/explain',{'endpoint_id':'not-present'})
        self.assertEqual(code,400)

    def test_static_app_and_security_headers(self):
        with urllib.request.urlopen(self.url,timeout=5) as response:
            text=response.read().decode()
            self.assertIn('Project 31',text)
            self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])

    def test_unavailable_model_rejected_before_starting_job(self):
        identifier=self.record['id']
        before=copy.deepcopy(storage.get(identifier))
        status={'available':False,'state':'missing_model','message':'Model missing.','action':'Run ollama pull gemma:2b.'}
        with patch('app.server.llm.model_status',return_value=status),patch('app.server.llm.explain') as generate:
            code,body,_=self.request('/api/projects/'+identifier+'/explain',{})
        self.assertEqual(code,503)
        self.assertIn('ollama pull',body['error'])
        generate.assert_not_called()
        self.assertEqual(storage.get(identifier),before)

    def test_busy_model_keeps_the_existing_job(self):
        with llm.LOCK,patch('app.server.llm.model_status',return_value={'available':True,'busy':True}):
            code,body,_=self.request('/api/projects/'+self.record['id']+'/explain',{})
        self.assertEqual(code,409)
        self.assertIn('already drafting',body['error'])


if __name__=='__main__':unittest.main()
