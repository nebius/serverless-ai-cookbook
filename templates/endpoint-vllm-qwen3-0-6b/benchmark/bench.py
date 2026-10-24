"""Standalone stdlib Qwen3 HTTP benchmark for an already deployed endpoint."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import ssl
import statistics
import threading
import time
from urllib.parse import urlsplit

PAYLOAD={'model':'Qwen/Qwen3-0.6B','messages':[{'role':'user','content':'Say hello in one short sentence.'}],
         'max_tokens':64,'temperature':0.2,'chat_template_kwargs':{'enable_thinking':False}}
BODY=json.dumps(PAYLOAD).encode()
ROUTE='/v1/chat/completions'


def utc(epoch):return datetime.fromtimestamp(epoch,timezone.utc).isoformat()
def percentile(values,fraction):return sorted(values)[max(0,math.ceil(len(values)*fraction)-1)] if values else None

def validate_url(base):
    url=urlsplit(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('HTTPS URL without embedded credentials, query or fragment required')
    url.port  # Reject malformed port numbers before starting workers.
    return url


def tls_context():
    explicit=os.environ.get('SSL_CERT_FILE')
    if explicit:return ssl.create_default_context(cafile=explicit)
    native=Path('/etc/ssl/cert.pem')
    return ssl.create_default_context(cafile=str(native)) if native.is_file() else ssl.create_default_context()


class Requester:
    def __init__(self,base,token,transport='persistent',timeout=1200):
        self.url=validate_url(base)
        if transport not in ('fresh','persistent'):raise ValueError('Unknown transport')
        self.token=token;self.transport=transport;self.timeout=timeout
        self.context=tls_context()
        if self.context.verify_mode!=ssl.CERT_REQUIRED or not self.context.check_hostname:raise ValueError('Verified TLS required')
        self.local=threading.local();self.lock=threading.Lock();self.connections=set()
    def discard(self,conn):
        if conn is None:return
        with self.lock:self.connections.discard(conn)
        try:conn.close()
        finally:
            if getattr(self.local,'connection',None) is conn:self.local.connection=None
    def connect(self):
        conn=http.client.HTTPSConnection(self.url.hostname,port=self.url.port,timeout=self.timeout,context=self.context)
        with self.lock:self.connections.add(conn)
        return conn
    def headers(self):
        headers={'Content-Type':'application/json','Connection':'keep-alive' if self.transport=='persistent' else 'close'}
        if self.token:headers['Authorization']='Bearer '+self.token
        return headers
    def request_once(self,index):
        conn=getattr(self.local,'connection',None) if self.transport=='persistent' else None
        preflight=conn is None and self.transport=='persistent';warm_start=time.monotonic();warm_error=None
        if preflight:
            try:
                conn=self.connect();conn.request('GET',self.url.path.rstrip('/')+'/v1/models',headers=self.headers())
                response=conn.getresponse()
                try:
                    response.read()
                    if response.status!=200 or getattr(response,'will_close',False):raise ConnectionError('Preflight failure')
                finally:response.close()
                self.local.connection=conn
            except Exception as error:warm_error=error;self.discard(conn);conn=None
        warm_seconds=time.monotonic()-warm_start if preflight else 0
        record={'request_index':index,'http_status':None,'content_type':'','response_complete':False,
                'generation_sent':False,'connection_preflight_performed':preflight,'connection_preflight_seconds':warm_seconds}
        raw=b'';response=None;broken=False;start_epoch=time.time();start=time.monotonic()
        try:
            if warm_error is not None:raise warm_error
            if conn is None:conn=self.connect()
            record['generation_sent']=True
            conn.request('POST',self.url.path.rstrip('/')+ROUTE,body=BODY,headers=self.headers())
            response=conn.getresponse();record['http_status']=response.status
            record['content_type']=response.getheader('Content-Type','')
            if self.token:record['content_type']=record['content_type'].replace(self.token,'[REDACTED]')
            raw=response.read()
            record['response_complete']=True;broken=bool(getattr(response,'will_close',False))
        except Exception as error:
            if isinstance(error,http.client.IncompleteRead):raw=error.partial
            record['transport_error']=type(error).__name__;broken=True
        finally:
            if response is not None:
                try:response.close()
                except Exception:record.update(transport_error='ResponseCloseError',response_complete=False);broken=True
        end=time.monotonic();end_epoch=time.time()
        if broken or self.transport=='fresh':self.discard(conn)
        record.update(started_at=utc(start_epoch),finished_at=utc(end_epoch),start_epoch=start_epoch,end_epoch=end_epoch,
            start_monotonic=start,end_monotonic=end,request_seconds=end-start,response_bytes=len(raw),
            response_sha256=hashlib.sha256(raw).hexdigest())
        record['http_success']=record['http_status']==200 and record['response_complete']
        return record,raw
    def close(self):
        with self.lock:connections=list(self.connections);self.connections.clear()
        for conn in connections:
            try:conn.close()
            except Exception:pass


def validate_response(raw):
    try:
        data=json.loads(raw);choice=data['choices'][0];text=choice['message']['content']
        if not isinstance(text,str) or not text.strip():raise ValueError('Empty final content')
        final=re.sub(r'<think>.*?</think>','',text,flags=re.S).strip()
        if '<think>' in final or not final:raise ValueError('Missing final answer')
        if choice.get('finish_reason')!='stop':raise ValueError('Generation did not finish with stop')
        result={'validated_success':True}
        usage=data.get('usage',{});tokens=usage.get('completion_tokens') if isinstance(usage,dict) else None
        if isinstance(tokens,int) and not isinstance(tokens,bool) and tokens>=0:result['completion_tokens']=tokens
        return result
    except (ValueError,KeyError,IndexError,TypeError):
        return {'validated_success':False,'validation_error':'Invalid JSON/chat final content or non-stop finish reason'}


def run_benchmark(base_url,token,out,concurrency=1,duration=60,min_requests=100,max_requests=10000,
                  transport='persistent',hourly_cost=None):
    validate_url(base_url)
    if (concurrency not in (1,8) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<60
        or not isinstance(min_requests,int) or min_requests<100 or not isinstance(max_requests,int) or max_requests<min_requests):
        raise ValueError('Use C1/C8, duration>=60 seconds, minimum>=100 requests and maximum>=minimum')
    if hourly_cost is not None and (not isinstance(hourly_cost,(int,float)) or not math.isfinite(hourly_cost) or hourly_cost<0):
        raise ValueError('Hourly list cost must be finite and nonnegative')
    output=Path(out)
    if output.exists() and any(output.iterdir()):raise ValueError('Output directory must be empty to preserve previous evidence')
    requester=Requester(base_url,token,transport);responses=output/'responses';responses.mkdir(parents=True,exist_ok=True)
    records=[];lock=threading.Lock();next_index=1;worker_errors=[]
    def worker():
        nonlocal next_index
        while True:
            with lock:
                if next_index>max_requests or (next_index>min_requests and time.monotonic()-start>=duration):return
                index=next_index;next_index+=1
            record,raw=requester.request_once(index)
            # Do not persist a server response that echoes the endpoint secret.
            sensitive=bool(token and token.encode() in raw)
            path=responses/(record['response_sha256']+'.json')
            with lock:
                record['response_secret_suppressed']=sensitive
                if not sensitive:
                    if not path.exists():path.write_bytes(raw)
                    record['response_artifact']=str(path.relative_to(output))
                records.append(record)
    start_epoch=time.time();start=time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures=[pool.submit(worker) for _ in range(concurrency)]
            for future in futures:
                try:future.result()
                except Exception as error:worker_errors.append(type(error).__name__)
    finally:requester.close()
    end=time.monotonic();end_epoch=time.time();seconds=end-start;records.sort(key=lambda r:r['request_index'])
    validation_start=time.monotonic();cache={}
    for record in records:
        record['validated_success']=False
        if record['http_success'] and not record['response_secret_suppressed']:
            digest=record['response_sha256']
            if digest not in cache:cache[digest]=validate_response((output/record['response_artifact']).read_bytes())
            record.update(cache[digest])
        else:record['validation_error']='HTTP/transport failure or secret-echo response suppressed'
    validation_seconds=time.monotonic()-validation_start
    http=[r for r in records if r['http_success']];valid=[r for r in records if r['validated_success']]
    tokens=[r['completion_tokens'] for r in valid if 'completion_tokens' in r]
    complete_usage=bool(valid) and len(tokens)==len(valid);cost=seconds*hourly_cost/3600 if hourly_cost is not None else None
    report={'payload':PAYLOAD,'route':ROUTE,'transport':transport,'concurrency':concurrency,
        'requested_minimum_count':min_requests,'requested_minimum_duration_seconds':duration,'max_requests':max_requests,
        'started_at':utc(start_epoch),'finished_at':utc(end_epoch),'start_epoch':start_epoch,'end_epoch':end_epoch,
        'phase_seconds':seconds,'validation_seconds':validation_seconds,'attempted':len(records),
        'scheduled':next_index-1,'worker_errors':worker_errors,'target_duration_met':seconds>=duration,
        'request_limit_reached':len(records)>=max_requests,'http_success':len(http),'validated_success':len(valid),
        'http_failed':len(records)-len(http),'invalid_http_success':len(http)-len(valid),
        'http_error_rate':(len(records)-len(http))/len(records) if records else None,
        'transport_failures':sum('transport_error' in record for record in records),
        'generation_transmission_attempts':sum(record['generation_sent'] for record in records),
        'p50_seconds':percentile([r['request_seconds'] for r in http],.5),'p95_seconds':percentile([r['request_seconds'] for r in http],.95),
        'validated_goodput_requests_per_second':len(valid)/seconds if seconds else None,
        'http_success_requests_per_second':len(http)/seconds if seconds else None,
        'usage':{'responses_with_usage':len(tokens),'coverage_fraction':len(tokens)/len(valid) if valid else None,
            'mean_completion_tokens':statistics.mean(tokens) if tokens else None,'median_completion_tokens':percentile(tokens,.5),
            'p95_completion_tokens':percentile(tokens,.95),'observed_total_completion_tokens':sum(tokens),
            'observed_completion_tokens_per_phase_second':sum(tokens)/seconds if tokens and seconds else None},
        'cost':{'basis':'Optional public USD on-demand list-rate estimate, not an invoice','hourly_usd':hourly_cost,
            'phase_usd':cost,'usd_per_1k_validated_requests':cost*1000/len(valid) if cost is not None and valid else None,
            'usd_per_1m_completion_tokens':cost*1e6/sum(tokens) if cost is not None and complete_usage and sum(tokens)>0 else None},
        'gpu_telemetry_captured':False,
        'limitations':['Request timing includes send through full body; parsing/hash/validation are excluded.',
            'Phase wall includes setup/preflight/hash/spooling and connection cleanup; validation is deferred.',
            'Persistent GET preflight warms one verified TLS connection per worker; fresh mode includes TLS setup in generation time.',
            'Use identical transport for both serving profiles; transport changes versus historical runs are not model gains.',
            'No generation retries. Reconnection happens only for a later counted request. Worker errors invalidate a complete run.',
            'API-reported token coverage is explicit; incomplete token rates are observed subtotals, not inferred totals.',
            'Technical stop/nonempty checks do not establish model quality. No GPU metrics, TTFT or TPOT are captured.']}
    (output/'requests.jsonl').write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in records))
    (output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return report


class SafeParser(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'Invalid benchmark arguments; use --help.\n')


if __name__=='__main__':
    parser=SafeParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--concurrency',type=int,choices=(1,8),default=1);parser.add_argument('--duration',type=float,default=60)
    parser.add_argument('--min-requests',type=int,default=100);parser.add_argument('--max-requests',type=int,default=10000)
    parser.add_argument('--transport',choices=('fresh','persistent'),default='persistent');parser.add_argument('--hourly-cost',type=float)
    args=parser.parse_args()
    try:
        report=run_benchmark(args.base_url,os.environ.get('NEBIUS_ENDPOINT_TOKEN',''),args.out,args.concurrency,
            args.duration,args.min_requests,args.max_requests,args.transport,args.hourly_cost)
    except Exception as error:
        parser.exit(2,'Benchmark failed ('+type(error).__name__+'); check arguments, TLS trust and output permissions.\n')
    print(json.dumps({key:report[key] for key in ('attempted','http_success','validated_success','p50_seconds','p95_seconds','target_duration_met','worker_errors')}))
    if report['worker_errors'] or report['scheduled']!=report['attempted'] or not report['target_duration_met']:raise SystemExit(1)
