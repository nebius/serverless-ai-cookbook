import importlib.util
import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'bench.py'
try:
    spec=importlib.util.spec_from_file_location('qwen_portable_bench',PATH)
    bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
except FileNotFoundError:bench=None

RAW=json.dumps({'choices':[{'message':{'content':'Hello!'},'finish_reason':'stop'}],
                'usage':{'completion_tokens':3}}).encode()
class Response:
    def __init__(self,status,body):self.status=status;self.body=body;self.will_close=False
    def read(self):return self.body
    def getheader(self,key,default=''):return 'application/json' if key=='Content-Type' else default
    def close(self):pass
class Connection:
    def __init__(self,results=None):self.results=list(results or []);self.methods=[];self.closed=False
    def request(self,method,path,body=None,headers=None):self.methods.append(method)
    def getresponse(self):
        value=self.results.pop(0) if self.results else (200,RAW)
        if isinstance(value,Exception):raise value
        return Response(*value)
    def close(self):self.closed=True

class BenchTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(bench,'standalone benchmark must exist')
    def test_nearest_rank_and_payload(self):
        self.assertEqual(bench.percentile(list(range(1,101)),.95),95)
        self.assertIsNone(bench.percentile([],.5))
        self.assertEqual(bench.PAYLOAD['max_tokens'],64)
        self.assertEqual(bench.PAYLOAD['temperature'],.2)
        self.assertFalse(bench.PAYLOAD['chat_template_kwargs']['enable_thinking'])
    def test_unsafe_urls_and_arguments(self):
        for url in ('http://example.test','https://user:pass@example.test','https://example.test?token=secret'):
            with self.subTest(url=url),self.assertRaises(ValueError):bench.validate_url(url)
        for options in ({'duration':0},{'min_requests':0},{'concurrency':2},{'max_requests':99},{'hourly_cost':-1}):
            with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):
                bench.run_benchmark('https://example.test','',tmp,**options)
    def test_http500_reset_count_once_and_persistent_connection_reuse(self):
        a=Connection([(200,b'{}'),(500,b'failed'),ConnectionResetError('secret disconnect')])
        b=Connection([(200,b'{}'),(200,RAW)])
        with patch.object(bench.http.client,'HTTPSConnection',side_effect=[a,b]):
            requester=bench.Requester('https://example.test','secret','persistent')
            first,_=requester.request_once(1);failure,_=requester.request_once(2)
            self.assertEqual(first['http_status'],500);self.assertFalse(failure['http_success'])
            self.assertNotIn('secret',json.dumps(failure));self.assertEqual(a.methods,['GET','POST','POST'])
            self.assertTrue(requester.request_once(3)[0]['http_success'])
            requester.close();self.assertTrue(a.closed and b.closed)
    def test_validation_and_finish_reason(self):
        self.assertTrue(bench.validate_response(RAW)['validated_success'])
        for body in (b'broken',b'{"choices":[{"message":{"content":""},"finish_reason":"stop"}]}',
                     b'{"choices":[{"message":{"content":"hello"},"finish_reason":"length"}]}'):
            self.assertFalse(bench.validate_response(body)['validated_success'])
    def test_request_cap_duration_and_saved_evidence(self):
        connections=[]
        def factory(*args,**kwargs):
            conn=Connection();connections.append(conn);return conn
        with tempfile.TemporaryDirectory() as tmp,patch.object(bench.http.client,'HTTPSConnection',side_effect=factory):
            report=bench.run_benchmark('https://example.test','secret',tmp,max_requests=100,hourly_cost=2)
            self.assertEqual(report['attempted'],100);self.assertEqual(report['validated_success'],100)
            self.assertTrue(report['request_limit_reached']);self.assertFalse(report['target_duration_met'])
            self.assertEqual(len(connections),1);self.assertTrue(connections[0].closed)
            self.assertEqual(len(list((Path(tmp)/'responses').glob('*'))),1)
            self.assertEqual(len((Path(tmp)/'requests.jsonl').read_text().splitlines()),100)
            self.assertNotIn('secret',(Path(tmp)/'summary.json').read_text())
            self.assertEqual(report['usage']['responses_with_usage'],100)
        ticks=iter(range(100000))
        with tempfile.TemporaryDirectory() as tmp,patch.object(bench.http.client,'HTTPSConnection',side_effect=factory),patch.object(bench.time,'monotonic',side_effect=lambda:next(ticks)):
            report=bench.run_benchmark('https://example.test','',tmp,max_requests=200)
            self.assertGreaterEqual(report['attempted'],100);self.assertTrue(report['target_duration_met'])
    def test_all_failures_have_undefined_success_latency_and_cost(self):
        conn=Connection([(200,b'{}')]+[(500,b'failed')]*100)
        with tempfile.TemporaryDirectory() as tmp,patch.object(bench.http.client,'HTTPSConnection',return_value=conn):
            report=bench.run_benchmark('https://example.test','',tmp,max_requests=100,hourly_cost=2)
            self.assertEqual(report['http_failed'],100)
            self.assertIsNone(report['p95_seconds'])
            self.assertIsNone(report['cost']['usd_per_1k_validated_requests'])
            self.assertEqual(conn.methods.count('POST'),100)

    def test_server_secret_echo_is_not_persisted(self):
        secret='sensitive-endpoint-token'
        body=json.dumps({'choices':[{'message':{'content':secret},'finish_reason':'stop'}]}).encode()
        def factory(*args,**kwargs):
            return Connection([(200,b'{}')]+[(200,body)]*100)
        with tempfile.TemporaryDirectory() as tmp,patch.object(bench.http.client,'HTTPSConnection',side_effect=factory):
            report=bench.run_benchmark('https://example.test',secret,tmp,max_requests=100)
            self.assertEqual(report['validated_success'],0)
            self.assertEqual(len(list((Path(tmp)/'responses').glob('*'))),0)
            self.assertNotIn(secret,(Path(tmp)/'requests.jsonl').read_text())
            self.assertNotIn(secret,(Path(tmp)/'summary.json').read_text())

    def test_post_timer_includes_full_body_but_excludes_persistent_get(self):
        import time
        class Delayed(Connection):
            def getresponse(self):
                response=super().getresponse();read=response.read
                def delayed():
                    time.sleep(.06 if self.methods[-1]=='GET' else .04)
                    return read()
                response.read=delayed;return response
        conn=Delayed([(200,b'{}'),(200,RAW)])
        with patch.object(bench.http.client,'HTTPSConnection',return_value=conn):
            requester=bench.Requester('https://example.test','','persistent')
            record,raw=requester.request_once(1);requester.close()
            self.assertGreaterEqual(record['request_seconds'],.035)
            self.assertLess(record['request_seconds'],.08)
            self.assertGreaterEqual(record['connection_preflight_seconds'],.055)
            self.assertEqual(record['response_bytes'],len(raw))

    def test_fresh_connections_have_no_unmeasured_preflight_and_tls_is_verified(self):
        made=[]
        def factory(*args,**kwargs):
            self.assertEqual(kwargs['context'].verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(kwargs['context'].check_hostname)
            conn=Connection();made.append(conn);return conn
        with patch.object(bench.http.client,'HTTPSConnection',side_effect=factory):
            requester=bench.Requester('https://example.test','','fresh')
            requester.request_once(1);requester.request_once(2);requester.close()
            self.assertEqual(len(made),2);self.assertTrue(all(c.methods==['POST'] and c.closed for c in made))

if __name__=='__main__':unittest.main()
