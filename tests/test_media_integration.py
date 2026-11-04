"""Exercise real encoders; video cases skip when FFmpeg is unavailable."""
import asyncio
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from app.image_processor import process_single_image
from app.video_processor import video_processor


@pytest.mark.parametrize('target', ['jpg', 'png', 'webp', 'avif', 'bmp', 'tiff', 'ico'])
def test_real_image_formats(tmp_path, target):
    source = tmp_path / 'source.png'
    Image.new('RGBA', (64, 48), (120, 40, 80, 100)).save(source)
    output = process_single_image(source, str(tmp_path / 'out'), target, 80, None, None)
    with Image.open(output) as image:
        image.load()
        assert image.width > 0 and image.height > 0
        if target in {'png', 'webp', 'avif', 'tiff'}:
            assert 'A' in image.getbands()


@pytest.fixture(scope='module')
def real_video(tmp_path_factory):
    if not video_processor.check_ffmpeg():
        pytest.skip('FFmpeg/FFprobe unavailable')
    root = tmp_path_factory.mktemp('video-formats')
    source = root / 'source.mkv'
    subprocess.run([video_processor.ffmpeg_path, '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc=size=63x47:rate=10', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=44100', '-t', '0.5',
                    '-c:v', 'ffv1', '-c:a', 'pcm_s16le', str(source)], check=True,
                   capture_output=True)
    return source


@pytest.mark.parametrize('target', ['mp4', 'mp4_hevc', 'mkv', 'webm', 'mov', 'avi', 'wmv', 'flv'])
def test_real_video_formats_and_audio_removal(real_video, tmp_path, target):
    success, message, output = asyncio.run(video_processor.process_video(
        real_video, tmp_path, target, 70, width=48, remove_audio=True, strip_metadata=True))
    assert success, message
    assert Path(output).stat().st_size > 0
    metadata = asyncio.run(video_processor.get_video_metadata(Path(output)))
    videos = [stream for stream in metadata['streams'] if stream['codec_type'] == 'video']
    assert len(videos) == 1
    assert videos[0]['width'] == 48
    assert all(stream['codec_type'] != 'audio' for stream in metadata['streams'])
