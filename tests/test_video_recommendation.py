from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import video_recommendation as vr


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, tzinfo=timezone.utc)
        self.e = {'id':'mark-1','origin':'book-1','source':'weread','kind':'highlight',
                  'occurred_at':self.now.isoformat(),'topics':['habit']}

    def test_wiki_copy_does_not_inflate_interest(self):
        copied = dict(self.e, id='wiki-copy', source='wiki')
        self.assertEqual(vr.rank_topics([self.e], self.now)[0]['score'],
                         vr.rank_topics([self.e, copied], self.now)[0]['score'])

    def test_decay_and_expired_inputs(self):
        old = dict(self.e, occurred_at=(self.now-timedelta(days=14)).isoformat())
        self.assertAlmostEqual(vr.rank_topics([old], self.now)[0]['score'], .3)
        old['occurred_at'] = (self.now-timedelta(days=91)).isoformat()
        self.assertEqual(vr.rank_topics([old], self.now), [])

    def test_machine_outputs_and_automation_are_not_interest(self):
        for flag in ('generated','automated','archived'):
            self.assertEqual(vr.rank_topics([dict(self.e, **{flag:True})], self.now), [])

    def test_watch_time_is_required_and_bounded(self):
        watch = dict(self.e, kind='watch')
        self.assertEqual(vr.rank_topics([watch], self.now), [])
        watch['engaged_seconds'] = 50000
        self.assertEqual(vr.rank_topics([watch], self.now)[0]['score'], .4)

    def test_source_flood_is_capped(self):
        many = [dict(self.e, id=str(i)) for i in range(100)]
        self.assertEqual(vr.rank_topics(many, self.now)[0]['score'], .6)
        independent = [dict(self.e, id=str(i), origin=str(i)) for i in range(100)]
        self.assertEqual(vr.rank_topics(independent, self.now)[0]['score'], 1.8)

    def test_candidate_quality_beats_popularity_and_seen_is_excluded(self):
        good = {'url':'https://www.youtube.com/watch?v=h35hy4LcVFw',
                'transcript_status':'complete','score_evidence':['cue 10'],
                'scores':dict.fromkeys(('relevance','novelty','substance','time_value'),4)}
        popular = dict(good, url='https://www.youtube.com/watch?v=AdKUJxjn-R8', views=1000000,
                       scores=dict.fromkeys(good['scores'],2))
        self.assertEqual(vr.select_candidate([popular,good])['url'], good['url'])
        self.assertIsNone(vr.select_candidate([popular,good], ['h35hy4LcVFw']))
        self.assertIsNone(vr.select_candidate([dict(good,transcript_status='partial')]))


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.db = vr.database(self.path / 'state.sqlite')
        self.transcript = self.path / 'transcript.json'
        self.transcript.write_text(json.dumps({'video_id':'AdKUJxjn-R8',
            'cues':[{'start':0,'duration':50,'text':'a'}, {'start':50,'duration':50,'text':'b'}]}))
        self.card = {'url':'https://www.youtube.com/watch?v=AdKUJxjn-R8',
                     'transcript_status':'complete','transcript_path':str(self.transcript),
                     'duration_seconds':100,'reviewed_cue_ranges':[[0,1]],
                     **{k:'synthetic' for k in ('title','reason','summary','highlights','source_coverage','limitations')}}

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def test_claim_prevents_concurrent_same_day_work(self):
        vr.begin(self.db, '2026-11-08')
        other = vr.database(self.path / 'state.sqlite')
        with self.assertRaises(sqlite3.IntegrityError): vr.begin(other, '2026-11-08')
        other.close()

    def test_missing_and_partial_captions_are_rejected(self):
        vr.begin(self.db, '2026-11-08')
        for change in ({'reviewed_cue_ranges':[[0,0]]}, {'duration_seconds':1000},
                       {'duration_seconds':None}, {'transcript_status':'partial'}):
            with self.assertRaises(ValueError): vr.finish(self.db, '2026-11-08', dict(self.card, **change))

    def test_prepared_is_not_delivered_and_video_deduplicates(self):
        vr.begin(self.db, '2026-11-08')
        result = vr.finish(self.db, '2026-11-08', self.card)
        self.assertEqual(result['state'], 'prepared')
        vr.begin(self.db, '2026-11-09')
        with self.assertRaises(sqlite3.IntegrityError): vr.finish(self.db, '2026-11-09', self.card)

    def test_upgrade_requires_stop(self):
        with patch.dict('os.environ', {'WEREAD_API_KEY':'test'}), patch.object(vr,'request_json',return_value={'upgrade_info':{'message':'update'}}):
            with self.assertRaisesRegex(RuntimeError,'upgrade required'): vr.weread('/readdata/detail')

    def test_comments_failure_does_not_hide_video_metadata(self):
        with patch.object(vr,'youtube',side_effect=[{'items':[{'id':'AdKUJxjn-R8'}]},RuntimeError('HTTP 403')]):
            result=vr.inspect_video(self.card['url'])
        self.assertEqual(result['video']['id'],'AdKUJxjn-R8')
        self.assertEqual(result['comments']['status'],'unavailable')


if __name__ == '__main__': unittest.main()
