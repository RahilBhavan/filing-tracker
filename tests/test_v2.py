import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from filing_tracker.core import compare, load_pair, TrackerError
from filing_tracker.numbers import compare_numbers, date_only_change
from filing_tracker.review_app import ReviewStore, create_server
from filing_tracker.alignment import members
from test_tracker import simple_pair, fixture

ROOT=Path(__file__).resolve().parents[1]

class Numbers(unittest.TestCase):
    def test_money_units_and_percent_points(self):
        n=compare_numbers('Revenue was $1 billion in 2023.','Revenue was $1,200 million in 2024.',2023,2024)['comparisons'][0]
        self.assertEqual(n['absolute_change'],200000000)
        self.assertEqual(n['relative_change_percent'],20)
        n=compare_numbers('The effective tax rate was 19%.','The effective tax rate was 18%.',2023,2024)['comparisons'][0]
        self.assertEqual(n['percentage_point_change'],-1)
        self.assertIsNone(n['relative_change_percent'])
    def test_dates_are_not_dollars(self):
        self.assertTrue(date_only_change('As of June 30, 2023','As of June 30, 2024'))
        self.assertFalse(date_only_change('Revenue $2023','Revenue $2024'))
        self.assertFalse(date_only_change('Revenue 2023 million','Revenue 2024 million'))
    def test_abstains_on_currency_quarters_and_duplicate_values(self):
        for a,b in [('Revenue $10 million.','Revenue €12 million.'),('Quarter revenue $10 million.','Quarter revenue $12 million.'),('Revenue $10 million and $11 million.','Revenue $12 million and $13 million.')]:
            result=compare_numbers(a,b,2023,2024)
            self.assertEqual(result['comparisons'],[])
            self.assertTrue(result['abstentions'])
    def test_respectively_uses_latest_period(self):
        a='Our effective tax rates were 19% and 16% for fiscal years 2023 and 2022, respectively.'
        b='Our effective tax rates were 18% and 19% for fiscal years 2024 and 2023, respectively.'
        # Supported singular/plural wording must both resolve the metric.
        result=compare_numbers(a,b,2023,2024)['comparisons']
        self.assertEqual(result[0]['absolute_change'],-1)

class Alignment(unittest.TestCase):
    def test_split_and_merge_preserve_members(self):
        a='Our cloud products serve business customers around the world.'
        b='Our security products protect customer data and critical systems.'
        for old,new in [([a+' '+b],[a,b]),([a,b],[a+' '+b])]:
            result=compare(simple_pair(old,new))
            group=[c for c in result['changes'] if c['method']=='adjacent-group']
            self.assertEqual(len(group),1)
            self.assertEqual(group[0]['kind'],'unchanged')
            self.assertEqual(len(members(group[0]['old']))+len(members(group[0]['new'])),3)
    def test_assumptions_link_without_asserting_direction(self):
        result=compare(fixture(),assumptions=[{'id':'cash','statement':'Liquidity remains adequate','terms':['credit facility'],'priority':'high'}])
        linked=[c for c in result['changes'] if c['assumption_links']]
        self.assertTrue(linked)
        self.assertIn('interpretation',linked[0]['assumption_links'][0])

class Review(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=ReviewStore(ROOT/'fixtures/development-pair.json',self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_persistence_stale_revision_and_history(self):
        change=next(c for c in self.store.result['changes'] if c['kind']!='unchanged')
        request={'revision':0,'action':'decision','id':change['id'],'decision':{'status':'accepted','note':'Reviewed source'}}
        self.store.update(request)
        with self.assertRaises(TrackerError): self.store.update(request)
        restored=ReviewStore(ROOT/'fixtures/development-pair.json',self.temp.name)
        self.assertEqual(restored.state['revision'],1)
        self.assertEqual(restored.state['review']['reviews'][change['id']]['status'],'accepted')
        self.assertEqual(len(restored.state['history']),1)
    def test_group_corrections_keep_all_citations(self):
        self.store.update({'revision':0,'action':'alignment','old':['risk-0001','risk-0002'],'new':['risk-0001','risk-0002']})
        grouped=next(c for c in self.store.result['changes'] if len(members(c['old']))==2)
        self.assertEqual(len(grouped['old_citations']),2)
        self.assertEqual(len(grouped['new_citations']),2)
        self.assertEqual(self.store.state['history'][-1]['action'],'alignment')
        for link in grouped['old_citations']+grouped['new_citations']:
            path,anchor=link.split('#')
            self.assertIn('id="'+anchor+'"',(self.store.directory/'report'/path).read_text())

    def test_invalid_decision_does_not_mutate(self):
        with self.assertRaises(TrackerError): self.store.update({'revision':0,'action':'decision','id':'unknown','decision':{}})
        self.assertEqual(self.store.state['revision'],0)
    def test_session_measurements(self):
        self.store.update({'revision':0,'action':'start_session','mode':'manual','reviewer':'Automated test only'})
        self.store.update({'revision':1,'action':'stop_session'})
        s=self.store.state['sessions'][0]
        self.assertGreaterEqual(s['elapsed_seconds'],0)
        self.assertEqual(s['alignment_corrections'],0)
    def test_http_token_host_and_traversal(self):
        server=create_server(self.store,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            self.assertEqual(urllib.request.urlopen(url+'/').status,200)
            for path in ['/report/../review-state.json','/report/%2e%2e/review-state.json']:
                with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(url+path)
                self.assertEqual(e.exception.code,403)
            request=urllib.request.Request(url+'/api/update',data=b'{}',headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(request)
            self.assertEqual(e.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(urllib.request.Request(url+'/',headers={'Host':'evil.example'}))
        finally: server.shutdown();server.server_close();thread.join()

class Corpus(unittest.TestCase):
    def test_original_hashes_and_exact_source_spans(self):
        for name in ['msft-2022-2023','msft-2023-2024','brk-2023-2024']:
            pair=load_pair(ROOT/'corpus'/f'{name}.json')
            for side in ['old','new']:
                self.assertTrue(pair[side]['blocks'])
                for b in pair[side]['blocks']:
                    self.assertEqual(pair[side]['text'][b['start']:b['end']],b['text'])
                    self.assertTrue(b['source_locator'])
