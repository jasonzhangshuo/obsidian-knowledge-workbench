function transcriptJobUrl(sender) {
  const url = new URL(sender.url);
  if (!url.port || url.hostname !== '127.0.0.1' || url.protocol !== 'http:' ||
      !/^\/youtube-transcript-job\/[a-f0-9]{48}$/.test(url.pathname)) {
    throw new Error('INVALID_TRANSCRIPT_JOB');
  }
  return url;
}

async function startTranscriptJob({ videoId }, sender) {
  transcriptJobUrl(sender);
  if (!/^[\w-]{11}$/.test(videoId || '')) throw new Error('INVALID_VIDEO_ID');

  const videoUrl = 'https://www.youtube.com/watch?v=' + videoId;
  const tab = await chrome.tabs.create({ url: videoUrl, active: false });
  try {
    const deadline = Date.now() + 25_000;
    while (Date.now() < deadline) {
      const result = await chrome.tabs.sendMessage(tab.id, { type: 'YTC_CLI_GET', videoId }).catch(() => null);
      if (result?.cues?.length) return { result };
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    return { result: { video_id: videoId, error: 'CAPTIONS_UNAVAILABLE：Chrome 未在时限内取得字幕轨' } };
  } finally {
    const current = await chrome.tabs.get(tab.id).catch(() => null);
    if (current?.url === videoUrl || current?.pendingUrl === videoUrl) {
      await chrome.tabs.remove(tab.id).catch(() => {});
    }
  }
}

async function closeTranscriptJob(sender) {
  const url = transcriptJobUrl(sender);
  const current = await chrome.tabs.get(sender.tab.id).catch(() => null);
  if (current?.url === url.href || current?.pendingUrl === url.href) {
    await chrome.tabs.remove(sender.tab.id).catch(() => {});
  }
  return {};
}
