import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch
import ci_pull_images as ci


class DockerPreparationTests(unittest.TestCase):
    def test_readiness_timeout_and_pull_failure_retry_before_success(self):
        responses=[subprocess.TimeoutExpired(['docker','info'],30),subprocess.CompletedProcess([],1),subprocess.CompletedProcess([],0)]
        with patch.object(ci.subprocess,'run',side_effect=responses) as run,patch.object(ci.time,'sleep') as sleep,contextlib.redirect_stdout(io.StringIO()):
            ci.retry(['docker','info'],30)
        self.assertEqual(run.call_count,3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[5,10])

    def test_failure_stays_failure_after_limit(self):
        with patch.object(ci.subprocess,'run',return_value=subprocess.CompletedProcess([],1)) as run,patch.object(ci.time,'sleep'),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(RuntimeError):
            ci.retry(['docker','pull','public-fixture'],120)
        self.assertEqual(run.call_count,3)

    def test_only_digest_pinned_public_images_are_selected(self):
        for target in ('main','immich'):
            images=ci.image_list(target)
            self.assertTrue(images)
            self.assertEqual(len(images),len(set(images)))
            self.assertTrue(all('@sha256:' in image for image in images))


if __name__=='__main__':unittest.main()
