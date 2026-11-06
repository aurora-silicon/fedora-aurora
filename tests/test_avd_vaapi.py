import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AvdVaapiPackaging(unittest.TestCase):
    def test_source_pin_and_driver_alias(self):
        source = json.loads((ROOT / "sources.json").read_text())["libva-v4l2-request"]
        self.assertEqual(source["commit"], "b318fcf4bd5e563e6ebc53953567a12ab39dcb24")
        self.assertEqual(source["sha256"], "4a8970530a82bd2d29a9956f582365807b9bba64cedd710ee771a070a8c5356b")
        spec = (ROOT / "packages/libva-v4l2-request/libva-v4l2-request.spec").read_text()
        self.assertIn(f"%global commit {source['commit']}", spec)
        self.assertIn("%meson -Dvendor-string=Aurora -Dstrip=false", spec)
        self.assertIn("ln -s v4l2_request_drv_video.so", spec)
        self.assertIn("%{_libdir}/dri/asahi_drv_video.so", spec)

    def test_base_image_installs_driver(self):
        path = ROOT / "images/configure.py"
        spec = importlib.util.spec_from_file_location("aurora_images", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        packages = module.PACKAGES["components/base.xml"][1]
        self.assertIn("libva-v4l2-request", packages)


if __name__ == "__main__":
    unittest.main()
