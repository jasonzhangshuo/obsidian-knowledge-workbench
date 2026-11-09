"""Ask the YouTube Chinese Chrome extension for a timed transcript."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit


VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}')
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com'}
MAX_RESULT_BYTES = 8 * 1024 * 1024
ASSETS = Path(__file__).with_name('youtube_transcript_extension')
PROJECT = Path(__file__).resolve().parents[1]
CHROME_APP = Path('/Applications/Google Chrome.app')
CHROME_USER_DATA = Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome'
CHROME_PROFILE_FILE = PROJECT / '.runtime' / 'youtube-transcript-profile'
SKILL_INSTALL_MARKER = '<!-- Installed by tools/youtube_transcript.py register. Edit the project skill. -->'


def normalize_video_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
        raise ValueError('请提供标准 HTTPS YouTube 视频链接')
    parts = parsed.path.strip('/').split('/')
    video_id = ''
    if parsed.hostname == 'youtu.be' and len(parts) == 1:
        video_id = parts[0]
    elif parsed.hostname in YOUTUBE_HOSTS:
        if parsed.path == '/watch':
            ids = parse_qs(parsed.query).get('v', [])
            video_id = ids[0] if len(ids) == 1 else ''
        elif len(parts) == 2 and parts[0] in {'shorts', 'live'}:
            video_id = parts[1]
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError('链接中没有可识别的 YouTube 视频 ID')
    return video_id


def validate_result(result, video_id):
    if not isinstance(result, dict) or result.get('video_id') != video_id:
        raise ValueError('Chrome 返回的视频 ID 与请求不一致')
    cues = result.get('cues')
    if not isinstance(cues, list) or not cues:
        raise ValueError('Chrome 没有返回可用字幕')
    for cue in cues:
        if not isinstance(cue, dict) or not isinstance(cue.get('text'), str) or not cue['text'].strip():
            raise ValueError('字幕片段缺少文本')
        for key in ('start', 'duration'):
            value = cue.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'字幕片段的 {key} 无效')
    cues = sorted(cues, key=lambda cue: cue['start'])
    return {
        'source': 'youtube_chrome_caption_track',
        'url': f'https://www.youtube.com/watch?v={video_id}',
        'video_id': video_id,
        'title': result.get('title'),
        'language': result.get('language'),
        'kind': result.get('kind'),
        'video_duration': result.get('video_duration'),
        'cue_count': len(cues),
        'first_start': cues[0]['start'],
        'last_end': max(cue['start'] + cue['duration'] for cue in cues),
        'cues': cues,
    }


def prepare_extension(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination.exists() or source in destination.parents:
        raise ValueError('扩展输出目录必须是源目录之外的新目录')
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest.get('name') != 'YouTube Chinese' or manifest.get('manifest_version') != 3:
        raise ValueError('源目录必须是已构建的 YouTube Chinese MV3 扩展')
    if not (source / 'shared' / 'queue.js').is_file():
        raise ValueError('请选择包含 shared/queue.js 的 dist/extension 构建目录')
    if 'http://127.0.0.1:8787/*' not in manifest.get('host_permissions', []):
        raise ValueError('扩展缺少原有的本地服务访问权限')
    manifest['content_scripts'].append({
        'matches': ['http://127.0.0.1/youtube-transcript-job/*'],
        'js': ['src/transcript-launch.js'],
        'run_at': 'document_idle',
    })
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        build = Path(temporary) / 'extension'
        shutil.copytree(source, build, ignore=shutil.ignore_patterns('.env*', '.git', '.DS_Store'))
        for name in ('transcript-launch.js', 'transcript-background.js'):
            shutil.copyfile(ASSETS / name, build / 'src' / name)
        background = build / 'src' / 'background.js'
        handler = "    case 'GET_SETTINGS':"
        code = background.read_text()
        if code.count(handler) != 1:
            raise ValueError('扩展的消息处理代码已经变化，需核对适配')
        background.write_text("importScripts('transcript-background.js');\n" + code.replace(
            handler, "    case 'YTC_CLI_START':\n      return startTranscriptJob(message, sender);\n"
            "    case 'YTC_CLI_FINISH':\n      return closeTranscriptJob(sender);\n" + handler,
        ))
        content = build / 'src' / 'content.js'
        marker = '  init();\n})();'
        code = content.read_text()
        if code.count(marker) != 1 or 'state.transcript = cues;' not in code:
            raise ValueError('扩展的字幕缓存代码已经变化，需核对适配')
        content.write_text(code.replace(marker, (ASSETS / 'transcript-content.js').read_text() + '\n' + marker))
        (build / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        build.rename(destination)
    return destination


def register_skill(vault=None, project=PROJECT):
    if vault is None:
        config = project / '.env'
        text = config.read_text() if config.is_file() else ''
        match = re.search(r'^\s*(?:export\s+)?OBSIDIAN_VAULT_PATH\s*=\s*(.+)$', text, re.M)
        if not match:
            raise ValueError('项目 .env 缺少 OBSIDIAN_VAULT_PATH，请传入 --vault')
        vault = Path(match[1].strip().strip('"\''))
    vault = vault.expanduser().resolve(strict=True)
    skill = (project / 'skills' / 'youtube-transcript').resolve(strict=True)
    if not (vault / '90-系统' / 'YouTube学习流程.md').is_file():
        raise ValueError('指定的 Vault 缺少 YouTube 学习流程文档')
    content = (skill / 'SKILL.md').read_text(encoding='utf-8').replace(
        '\n---\n', '\n---\n\n' + SKILL_INSTALL_MARKER + '\n', 1,
    )
    if SKILL_INSTALL_MARKER not in content:
        raise ValueError('项目 Skill 缺少 YAML frontmatter')
    entries = [parent / skill.name for parent in (
        project / '.agents' / 'skills', vault / '.agents' / 'skills', vault / '.claude' / 'skills',
    )]
    for entry in entries:
        if entry.is_symlink():
            if entry.resolve() != skill:
                raise ValueError(f'Skill 入口已存在：{entry}')
        elif entry.exists():
            installed = entry / 'SKILL.md'
            if installed.is_symlink() or not installed.is_file() or SKILL_INSTALL_MARKER not in installed.read_text(encoding='utf-8'):
                raise ValueError(f'Skill 入口已存在：{entry}')
    for entry in entries:
        entry.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.youtube-transcript-', dir=entry.parent) as temporary:
            prepared = Path(temporary) / 'skill'
            prepared.mkdir()
            staged_file = prepared / 'SKILL.md'
            staged_file.write_text(content, encoding='utf-8')
            if entry.is_symlink():
                old_target = entry.readlink()
                entry.unlink()
                try:
                    prepared.rename(entry)
                except OSError:
                    if not entry.exists() and not entry.is_symlink():
                        entry.symlink_to(old_target, target_is_directory=True)
                    raise
            elif entry.exists():
                staged_file.replace(entry / 'SKILL.md')
            else:
                prepared.rename(entry)
    return entries


def chrome_launch_command(url):
    if not CHROME_PROFILE_FILE.exists():
        return ['/usr/bin/open', '-a', 'Google Chrome', url]
    profile = CHROME_PROFILE_FILE.read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'(?:Default|Profile [0-9]+)', profile):
        raise ValueError('YouTube 字幕工具的 Chrome 个人资料目录配置无效')
    if not (CHROME_USER_DATA / profile / 'Preferences').is_file():
        raise ValueError(f'找不到字幕工具配置的 Chrome 个人资料目录：{profile}')
    return ['/usr/bin/open', '-n', '-a', str(CHROME_APP), '--args', f'--profile-directory={profile}', url]


def fetch_transcript(video_id, timeout=45):
    path = '/youtube-transcript-job/' + secrets.token_hex(24)
    result = None

    class JobHandler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(4)
            super().setup()

        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path != path:
                self.send_error(404)
                return
            html = (f'<!doctype html><meta charset="utf-8"><title>YouTube 字幕任务</title>'
                    f'<meta name="youtube-transcript-video-id" content="{video_id}">'
                    '<p>正在等待 YouTube Chinese 扩展获取字幕…</p>').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(html)

        def do_POST(self):
            nonlocal result
            if self.path != path:
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_RESULT_BYTES:
                    raise ValueError('字幕响应大小不在允许范围')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict) or payload.get('video_id') != video_id:
                    raise ValueError('Chrome 返回的视频 ID 与请求不一致')
                error = payload.get('error')
                result = {'error': error} if isinstance(error, str) else validate_result(payload, video_id)
            except (ValueError, OSError, OverflowError):
                self.send_error(400)
                return
            self.send_response(204)
            self.end_headers()

    try:
        server = ThreadingHTTPServer(('127.0.0.1', 0), JobHandler)
    except PermissionError as error:
        raise RuntimeError('LOCAL_BRIDGE_DENIED：当前客户端不允许监听本机回环端口') from error
    with server:
        server.timeout = 0.5
        launch_url = f'http://127.0.0.1:{server.server_port}{path}'
        subprocess.run(chrome_launch_command(launch_url), check=True, timeout=8)
        deadline = time.monotonic() + timeout
        while result is None and time.monotonic() < deadline:
            server.handle_request()
    if result is None:
        raise RuntimeError('EXTENSION_TIMEOUT：Chrome 扩展未回传，请确认已加载带 CLI 接口的版本')
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fetch = commands.add_parser('fetch', help='通过 Chrome 扩展获取带时间戳的字幕 JSON')
    fetch.add_argument('url')
    prepare = commands.add_parser('prepare', help='从已有扩展构建目录生成支持 CLI 的副本')
    prepare.add_argument('source', type=Path)
    prepare.add_argument('destination', type=Path)
    register = commands.add_parser('register', help='将同一个 Skill 注册到项目与 Claudian')
    register.add_argument('--vault', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            print(prepare_extension(args.source, args.destination))
        elif args.command == 'register':
            for link in register_skill(args.vault):
                print(link)
        else:
            print(json.dumps(fetch_transcript(normalize_video_url(args.url)), ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
