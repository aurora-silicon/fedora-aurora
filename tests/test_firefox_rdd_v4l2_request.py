from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIREFOX = ROOT / "docs" / "firefox"


class FirefoxRddV4l2RequestTests(unittest.TestCase):
    def test_seccomp_is_exact_not_media_family_wide(self):
        patch = (FIREFOX / "0001-rdd-v4l2-request.patch").read_text()
        block = patch.split("Only the four media/request operations", 1)[1]
        names = re.findall(r"MEDIA(?:_REQUEST)?_IOC_[A-Z_]+", block)
        self.assertEqual(
            names[:4],
            [
                "MEDIA_IOC_G_TOPOLOGY",
                "MEDIA_IOC_REQUEST_ALLOC",
                "MEDIA_REQUEST_IOC_QUEUE",
                "MEDIA_REQUEST_IOC_REINIT",
            ],
        )
        self.assertNotIn("kMediaType", patch)

    def test_broker_does_not_grant_media_prefix(self):
        patch = (FIREFOX / "0001-rdd-v4l2-request.patch").read_text()
        self.assertIn("aM2mDevices.Contains", patch)
        self.assertIn("policy->AddPath(rdwr, path.get());", patch)
        self.assertNotRegex(patch, r"Add(?:Tree|Prefix|FilePrefix)\([^\n]*media")

    def test_fedora_delta_is_opt_in_and_pinned(self):
        delta = (FIREFOX / "fedora-44-157.spec.patch").read_text()
        preparer = (FIREFOX / "prepare-fedora.py").read_text()
        self.assertIn("%bcond avd_request 0", delta)
        self.assertIn("--with avd_request", delta)
        self.assertIn("1465e7dfc36e96ec3825c12f3dbed41c426e080d", preparer)
        self.assertIn("bc4c75cf7bfbd63781433fa28c97cb01f5433acf114b483015cd7abd56ebc807", preparer)


if __name__ == "__main__":
    unittest.main()
