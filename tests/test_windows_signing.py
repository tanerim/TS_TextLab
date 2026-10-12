"""Check the signing boundary: staged inputs, immutable originals, fail closed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage_module = load('stage_windows_binaries')
installer_module = load('create_desktop_installer')


class WindowsSigningTests(unittest.TestCase):
    def test_both_formats_receive_signed_copies_without_mutating_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'environment' / 'extension.PYD'
            source.parent.mkdir()
            source.write_bytes(b'original')
            data = root / 'model.json'
            data.write_text('{}')
            toc = [('pkg/extension.PYD', str(source), 'EXTENSION')]
            datas = [('copy.PYD', str(source), 'DATA'), ('model.json', str(data), 'DATA')]

            def sign(command, **kwargs):
                stage = Path(command[command.index('-Path') + 1])
                for path in stage.rglob('*.PYD'):
                    path.write_bytes(b'signed')

            with patch.object(stage_module.subprocess, 'run', side_effect=sign):
                binaries, staged_datas = stage_module.stage_and_sign((toc, datas), root)
            self.assertEqual(source.read_bytes(), b'original')
            self.assertEqual(Path(binaries[0][1]).read_bytes(), b'signed')
            self.assertEqual(binaries[0][1], staged_datas[0][1])
            self.assertEqual(staged_datas[1], datas[1])
            self.assertEqual(toc[0][1], str(source))

    def test_signing_failure_stops_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dll = root / 'test.dll'
            dll.write_bytes(b'original')
            with patch.object(stage_module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'pwsh')):
                with self.assertRaises(subprocess.CalledProcessError):
                    stage_module.stage_and_sign(([('test.dll', str(dll), 'BINARY')],), root)
            self.assertEqual(dll.read_bytes(), b'original')

    def test_required_signing_fails_before_executing_any_download(self):
        with patch.dict(installer_module.os.environ, {}, clear=True), patch.object(installer_module, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'requires configured code signing'):
                installer_module.windows('test', require_signing=True)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
