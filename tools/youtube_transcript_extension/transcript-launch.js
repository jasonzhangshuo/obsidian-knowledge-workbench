(async () => {
  if (location.hostname !== '127.0.0.1' || !/^\/youtube-transcript-job\/[a-f0-9]{48}$/.test(location.pathname)) return;
  const videoId = document.querySelector('meta[name="youtube-transcript-video-id"]')?.content;
  if (!/^[\w-]{11}$/.test(videoId || '')) return;

  let result;
  try {
    const response = await chrome.runtime.sendMessage({ type: 'YTC_CLI_START', videoId });
    if (!response?.ok || !response.result) throw new Error(response?.error?.message || 'EXTENSION_NO_RESULT');
    result = response.result;
  } catch (error) {
    result = { video_id: videoId, error: error.message };
  }

  try {
    const response = await fetch(location.href, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(result),
    });
    if (!response.ok) throw new Error('TRANSCRIPT_CALLBACK_HTTP_' + response.status);
    document.body.textContent = result.error || '字幕已交回命令行。';
    if (!result.error) chrome.runtime.sendMessage({ type: 'YTC_CLI_FINISH' }).catch(() => {});
  } catch (error) {
    document.body.textContent = '字幕回传失败：' + error.message;
  }
})();
