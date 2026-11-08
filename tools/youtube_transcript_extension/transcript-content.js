  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== 'YTC_CLI_GET') return;
    const videoId = new URL(location.href).searchParams.get('v');
    if (videoId !== message.videoId || !state.transcript.length) return;
    const track = new URL(state.transcriptUrl).searchParams;
    if (track.has('v') && track.get('v') !== videoId) return;
    sendResponse({
      video_id: videoId,
      title: document.querySelector('meta[name="title"]')?.content || document.title,
      language: track.get('lang'),
      kind: track.get('kind') || 'unspecified',
      video_duration: Number.isFinite(state.video?.duration) ? state.video.duration : null,
      cues: state.transcript,
    });
  });
