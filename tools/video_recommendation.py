"""Evidence ranking and private daily receipts for the video recommendation skill.

Semantic extraction/search/transcript review run in Codex, not in this CLI.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from youtube_transcript import normalize_video_url, validate_result

TZ = ZoneInfo('Asia/Shanghai')
BASE = {'question': 1.0, 'reflection': .85, 'highlight': .6,
        'reading': .45, 'watch': .4, 'visit': .1, 'wiki': .35}


def timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Evidence timestamps must include a timezone')
    return result


def rank_topics(evidence, now=None):
    """Deduplicate provenance before recency decay; cap one origin per topic.

    origin is the original book/video/question, not a replicated wiki path.
    These are inspectable heuristics, not learned probabilities.
    """
    now = now or datetime.now(timezone.utc)
    groups = {}
    for e in evidence:
        if e.get('generated') or e.get('automated') or e.get('archived'):
            continue
        kind = e['kind']
        if kind not in BASE:
            raise ValueError('Unknown evidence kind')
        age = (now - timestamp(e['occurred_at'])).total_seconds() / 86400
        if age < -1 or age > 90:
            continue
        confidence = float(e.get('confidence', 1))
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('Confidence must be in [0, 1]')
        strength = BASE[kind] * confidence * 2 ** (-max(0, age) / 14)
        if kind in ('watch', 'reading'):
            seconds = float(e.get('engaged_seconds', 0))
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError('Invalid engaged seconds')
            strength *= min(1, seconds / 1200)
        for topic in set(e['topics']):
            key = (topic, e['origin'])
            if key not in groups or strength > groups[key]['weight']:
                groups[key] = {'weight': strength, 'evidence_id': e['id'],
                               'origin': e['origin'], 'source': e['source']}
    topics = {}
    for (topic, _), item in groups.items():
        topics.setdefault(topic, []).append(item)
    result = []
    for topic, items in topics.items():
        items.sort(key=lambda item: (-item['weight'], item['evidence_id']))
        # Three independent origins suffice; a high volume source cannot swamp ranking.
        score = sum(item['weight'] for item in items[:3])
        if score >= .12:
            result.append({'topic': topic, 'score': round(score, 4), 'evidence': items[:3]})
    return sorted(result, key=lambda item: (-item['score'], item['topic']))


def select_candidate(candidates, seen=()):
    """Rank agent-reviewed candidates; popularity is deliberately not an input."""
    ranked = []
    for item in candidates:
        video_id = normalize_video_url(item['url'])
        if video_id in seen or item.get('transcript_status') != 'complete':
            continue
        values = [item['scores'][key] for key in ('relevance', 'novelty', 'substance', 'time_value')]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 5 for v in values):
            raise ValueError('Candidate scores must be finite numbers in [0, 5]')
        score = sum(v * w for v, w in zip(values, (.4, .25, .25, .1)))
        if score >= 3.5 and item.get('score_evidence'):
            ranked.append({**item, 'score': round(score, 3)})
    ranked.sort(key=lambda item: (-item['score'], item['url']))
    return ranked[0] if ranked else None


def request_json(url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        # Do not print request URL: it can contain an API key.
        raise RuntimeError(f'HTTP {error.code}; source unavailable') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Network error; source unavailable') from None
    return data


def weread(api, **params):
    key = os.environ.get('WEREAD_API_KEY')
    if not key:
        raise RuntimeError('WEREAD_API_KEY unavailable')
    data = request_json('https://i.weread.qq.com/api/agent/gateway',
                        {'api_name': api, 'skill_version': '1.0.5', **params},
                        {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    if 'upgrade_info' in data:
        raise RuntimeError('WeRead upgrade required: ' + str(data['upgrade_info'].get('message', '')))
    if data.get('errcode'):
        raise RuntimeError('WeRead error ' + str(data['errcode']))
    return data


def collect_weread():
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).timestamp()
    # Current and previous natural week: useful even when today is Monday.
    periods = [weread('/readdata/detail', mode='weekly', baseTime=base)
               for base in (0, int((now - timedelta(days=7)).timestamp()))]
    notebooks = weread('/user/notebooks', count=20)
    recent = [row for row in notebooks.get('books', []) if row.get('sort', 0) >= cutoff]
    books = {row['bookId']: row.get('book', {}) for row in recent[:5]}
    for period in periods:
        for row in period.get('readLongest', []):
            book = row.get('book', {})
            if book.get('bookId'):
                books[book['bookId']] = book
    notes = []
    for book_id, book in list(books.items())[:5]:
        marks = weread('/book/bookmarklist', bookId=book_id)
        reviews = weread('/review/list/mine', bookid=book_id, count=20, synckey=0)
        notes.append({'book_id': book_id, 'title': book.get('title'),
                      'highlights': [{k:r.get(k) for k in ('bookmarkId','markText','createTime','chapterUid','range')}
                                     for r in marks.get('updated', []) if r.get('createTime', 0) >= cutoff],
                      'reflections': [{k:r['review'].get(k) for k in ('reviewId','content','abstract','createTime','chapterUid','range')}
                                      for r in reviews.get('reviews', []) if r.get('review', {}).get('createTime', 0) >= cutoff],
                      'reviews_has_more': bool(reviews.get('hasMore'))})
    return {'fetched_at': now.isoformat(), 'scope': 'two natural weeks; recent 30-day notes; at most 5 books',
            'notebooks_has_more': bool(notebooks.get('hasMore')),
            'books_omitted': max(0, len(books)-5),
            'periods': [{'base_time': p.get('baseTime'), 'total_read_seconds': p.get('totalReadTime'),
                         'books': [{'id': r.get('book', {}).get('bookId'),
                                    'title': r.get('book', {}).get('title'),
                                    'read_seconds': r.get('readTime')}
                                   for r in p.get('readLongest', [])]} for p in periods], 'notes': notes}


def youtube(resource, **params):
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key:
        raise RuntimeError('YOUTUBE_API_KEY unavailable; use public web search and page evidence')
    return request_json('https://www.googleapis.com/youtube/v3/' + resource + '?' +
                        urllib.parse.urlencode({'key': key, **params}))


def inspect_video(url):
    video_id = normalize_video_url(url)
    video = youtube('videos', id=video_id, part='snippet,contentDetails,statistics')
    if not video.get('items'):
        raise RuntimeError('Video unavailable')
    try:
        comments = youtube('commentThreads', videoId=video_id, part='snippet',
                           order='relevance', maxResults=10, textFormat='plainText')
        comments = {'status': 'available', 'items': comments.get('items', [])}
    except RuntimeError as error:
        comments = {'status': 'unavailable', 'reason': str(error)}
    return {'fetched_at': datetime.now(timezone.utc).isoformat(),
            'video': video['items'][0], 'comments': comments}


def database(path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=5)
    os.chmod(path, 0o600)
    db.execute('CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, state TEXT, video_id TEXT UNIQUE, payload TEXT)')
    return db


def begin(db, day):
    with db:
        db.execute("INSERT INTO days VALUES (?, 'running', NULL, NULL)", (day,))
    return {'day': day, 'state': 'running'}


def finish(db, day, card):
    video_id = normalize_video_url(card['url'])
    if card.get('transcript_status') != 'complete' or not card.get('transcript_path'):
        raise ValueError('A reviewed transcript is required')
    transcript = validate_result(json.loads(Path(card['transcript_path']).read_text()), video_id)
    duration = card.get('duration_seconds') or transcript.get('video_duration')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Verified video duration is required')
    last_end = max(c['start'] + c['duration'] for c in transcript['cues'])
    first_start = min(c['start'] for c in transcript['cues'])
    if first_start > min(60, duration * .15) or last_end < duration * .9:
        raise ValueError('Transcript coverage is incomplete')
    count = len(transcript['cues'])
    reviewed = set()
    for first, last in card.get('reviewed_cue_ranges', []):
        if not 0 <= first <= last < count:
            raise ValueError('Invalid reviewed cue range')
        reviewed.update(range(first, last + 1))
    if len(reviewed) != count:
        raise ValueError('Transcript has unreviewed cues')
    for field in ('title', 'reason', 'summary', 'highlights', 'source_coverage', 'limitations'):
        if not card.get(field):
            raise ValueError('Missing recommendation field: ' + field)
    with db:
        result = db.execute("UPDATE days SET state='prepared',video_id=?,payload=? WHERE day=? AND state='running'",
                            (video_id, json.dumps(card, ensure_ascii=False), day))
        if result.rowcount != 1:
            raise ValueError('No running daily claim')
    # prepared means ready for current-thread output, not user received/read.
    return {'day': day, 'state': 'prepared', 'video_id': video_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('weread')
    rank = commands.add_parser('rank'); rank.add_argument('file', type=Path)
    select = commands.add_parser('select'); select.add_argument('file', type=Path)
    select.add_argument('--db', required=True, type=Path)
    search = commands.add_parser('search'); search.add_argument('query')
    video = commands.add_parser('video'); video.add_argument('url')
    for name in ('status', 'begin', 'finish', 'fail'):
        command = commands.add_parser(name)
        command.add_argument('--db', required=True, type=Path)
        command.add_argument('--day', default=datetime.now(TZ).date().isoformat())
        if name == 'finish': command.add_argument('--card', required=True, type=Path)
        if name == 'fail': command.add_argument('--reason', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'weread': result = collect_weread()
        elif args.command == 'rank': result = rank_topics(json.loads(args.file.read_text()))
        elif args.command == 'select':
            with database(args.db) as db:
                seen = [r[0] for r in db.execute('SELECT video_id FROM days WHERE video_id IS NOT NULL')]
            result = select_candidate(json.loads(args.file.read_text()), seen)
        elif args.command == 'search':
            result = youtube('search', q=args.query, type='video', part='snippet', maxResults=10)
        elif args.command == 'video': result = inspect_video(args.url)
        else:
            with database(args.db) as db:
                if args.command == 'begin': result = begin(db, args.day)
                elif args.command == 'finish': result = finish(db, args.day, json.loads(args.card.read_text()))
                elif args.command == 'fail':
                    changed = db.execute("UPDATE days SET state='failed',payload=? WHERE day=? AND state='running'",
                                         (json.dumps({'reason': args.reason}), args.day)).rowcount
                    result = {'updated': changed}
                else:
                    result = [dict(zip(('day','state','video_id'), row)) for row in
                              db.execute('SELECT day,state,video_id FROM days ORDER BY day DESC LIMIT 90')]
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, KeyError, OSError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
