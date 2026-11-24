"""FFmpeg and gst-plugins-good are Fedora's recipes plus the V4L2 ProRes patches."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fedoralib  # noqa: E402

FFMPEG = ['0001-avcodec-v4l2_buffers-use-the-driver-s-strides-for-si.patch',
          '0002-avcodec-v4l2_context-pick-the-raw-V4L2-format-the-dr.patch',
          '0003-avcodec-v4l2_m2m-add-ProRes-decoder-and-encoder.patch']


class ProResV4l2Tests(unittest.TestCase):
    def test_ffmpeg_applies_the_patches_and_builds_the_codecs(self):
        for fedora, release in ((44, '3'), (45, '4')):
            files = fedoralib.recipe_files(ROOT, 'ffmpeg', fedora)
            spec = files['ffmpeg.spec'].read_text()
            with self.subTest(fedora=fedora):
                self.assertRegex(spec, rf'(?m)^Release:\s+{release}%\{{\?dist\}}\.aurora[1-9][0-9]*$')
                self.assertEqual(re.findall(r'(?m)^Patch90\d:\s+(\S+)$', spec), FFMPEG)
                for patch in FFMPEG:
                    self.assertIn(patch, files)
                self.assertIn('%autosetup -S git_am', spec)
                self.assertIn('    --enable-v4l2-m2m \\', spec)
                self.assertIn('grep -q "#define CONFIG_PRORES_V4L2M2M_${i} 1" config_components.h', spec)
                for kind in ('enable_decoders', 'enable_encoders'):
                    names = [line.split()[0] for line in files[kind].read_text().splitlines() if line.strip()]
                    self.assertIn('prores_v4l2m2m', names)
                    self.assertIn('prores', names)
                pin = json.loads(files['distgit.json'].read_text())
                self.assertEqual(pin['branch'], f'f{fedora}')
                self.assertRegex(pin['commit'], r'^[0-9a-f]{40}$')

    def test_gst_plugins_good_applies_the_patch(self):
        for fedora in (44, 45):
            files = fedoralib.recipe_files(ROOT, 'gstreamer1-plugins-good', fedora)
            spec = files['gstreamer1-plugins-good.spec'].read_text()
            with self.subTest(fedora=fedora):
                self.assertRegex(spec, r'(?m)^Release:\s+1%\{\?dist\}\.aurora1$')
                self.assertRegex(spec, r'(?m)^Patch900:\s+0001-v4l2-add-ProRes-decoder-and-encoder\.patch$')
                self.assertRegex(spec, r'(?m)^Patch901:\s+0002-v4l2videodec-switch-to-a-supported-capture-format-be\.patch$')
                self.assertIn('%autosetup -p1 -n gst-plugins-good-%{version}', spec)


if __name__ == '__main__':
    unittest.main()
