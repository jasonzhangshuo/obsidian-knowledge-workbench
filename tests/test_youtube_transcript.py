import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.youtube_transcript import chrome_launch_command, normalize_video_url, register_skill, validate_result


class YouTubeTranscriptTests(unittest.TestCase):
    def test_browser_launch_targets_the_configured_profile_even_when_chrome_is_open(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'profile'
            profile = root / 'Profile 3'
            profile.mkdir()
            (profile / 'Preferences').touch()
            url = 'http://127.0.0.1:55000/youtube-transcript-job/example'
            with patch('tools.youtube_transcript.CHROME_PROFILE_FILE', config), patch('tools.youtube_transcript.CHROME_USER_DATA', root):
                self.assertEqual(chrome_launch_command(url), ['/usr/bin/open', '-a', 'Google Chrome', url])
                config.write_text('Profile 3\n')
                command = chrome_launch_command(url)
                self.assertIn('-n', command)
                self.assertEqual(command[-3:], ['--args', '--profile-directory=Profile 3', url])
                config.write_text('Profile 9\n')
                with self.assertRaisesRegex(ValueError, 'Profile 9'):
                    chrome_launch_command(url)

    def test_only_supported_youtube_urls_produce_a_video_id(self):
        self.assertEqual(normalize_video_url('https://youtu.be/8dHEG7WxR4c?t=1'), '8dHEG7WxR4c')
        self.assertEqual(normalize_video_url('https://www.youtube.com/watch?v=8dHEG7WxR4c'), '8dHEG7WxR4c')
        with self.assertRaises(ValueError):
            normalize_video_url('https://www.youtube.com.example.com/watch?v=8dHEG7WxR4c')

    def test_result_is_bound_to_the_requested_video_and_contains_real_cues(self):
        result = {
            'video_id': '8dHEG7WxR4c', 'language': 'en', 'kind': 'asr', 'title': 'Example',
            'cues': [{'start': 0, 'duration': 2.5, 'text': 'Example caption'}],
        }
        self.assertEqual(validate_result(result, '8dHEG7WxR4c')['cues'], result['cues'])
        with self.assertRaises(ValueError):
            validate_result(result, 'PRFzRtzhZrw')
        with self.assertRaises(ValueError):
            validate_result(dict(result, cues=[]), '8dHEG7WxR4c')
        with self.assertRaises(ValueError):
            validate_result(dict(result, cues=[{'start': float('nan'), 'duration': 1, 'text': 'x'}]), '8dHEG7WxR4c')

    def test_registration_replaces_old_links_with_readable_skill_files(self):
        with TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            vault = Path(directory) / 'vault'
            skill = project / 'skills' / 'youtube-transcript'
            skill.mkdir(parents=True)
            source = skill / 'SKILL.md'
            source.write_text('---\nname: youtube-transcript\ndescription: Shared skill\n---\n\nOld instructions\n')
            (vault / '90-系统').mkdir(parents=True)
            (vault / '90-系统' / 'YouTube学习流程.md').touch()
            claude_entry = vault / '.claude' / 'skills' / 'youtube-transcript'
            claude_entry.parent.mkdir(parents=True)
            claude_entry.symlink_to(skill, target_is_directory=True)
            register_skill(vault, project)
            source.write_text(source.read_text().replace('Old instructions', 'Updated instructions'))
            register_skill(vault, project)
            for parent in (project / '.agents', vault / '.agents', vault / '.claude'):
                entry = parent / 'skills' / 'youtube-transcript'
                self.assertFalse(entry.is_symlink())
                self.assertIn('Updated instructions', (entry / 'SKILL.md').read_text())


if __name__ == '__main__':
    unittest.main()
