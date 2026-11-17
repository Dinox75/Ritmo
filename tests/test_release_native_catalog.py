import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
SPEC = importlib.util.spec_from_file_location('release_native_catalog', Path(__file__).parents[1] / 'scripts/release_native_catalog.py')
catalog_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_tool)

class NativeCatalogTests(unittest.TestCase):
    def test_exact_python_base_hash_bound_to_receipt_not_claimed_vendor_filehash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / 'base'
            (base / 'DLLs').mkdir(parents=True)
            (base / 'python314.dll').write_bytes(b'verified installed bytes')
            (base / 'DLLs/unknown.dll').write_bytes(b'unknown')
            vendor = root / 'vendor.json'
            vendor.write_text(json.dumps(dict(packages=[dict(SPDXID='SPDXRef-cpython',name='CPython',versionInfo='3.14.10',licenseConcluded='PSF-2.0',externalRefs=[], checksums=[dict(algorithm='SHA256',checksumValue=catalog_tool.INSTALLER_SHA256)])],files=[])))
            receipt = dict(installer_sha256=catalog_tool.INSTALLER_SHA256, signature_status='Valid', signer_subject='CN=Python Software Foundation', source_url=catalog_tool.INSTALLER_URL, version='3.14.10')
            rules = dict(components=[dict(name='CPython', vendor_package='CPython', version='3.14.10', patterns=['python314.dll'],license='PSF-2.0',notices=[], evidence_urls=['https://www.python.org/'])])
            catalog = catalog_tool.create_catalog(base, vendor, receipt, rules)
            self.assertEqual(catalog['components'][0]['file_hashes'], [catalog_tool.file_sha(base / 'python314.dll')])
            self.assertEqual(catalog['unmapped_base_files'][0]['name'], 'unknown.dll')
            self.assertIn('not vendor-provided binary file hashes', catalog['limitations'][0])
            self.assertNotIn(str(base), json.dumps(catalog))
            receipt['signature_status'] = 'NotSigned'
            with self.assertRaises(ValueError):
                catalog_tool.create_catalog(base, vendor, receipt, rules)

    def test_vendor_installer_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vendor = root / 'vendor.json'
            vendor.write_text(json.dumps(dict(packages=[dict(name='CPython',versionInfo='3.14.10',checksums=[dict(algorithm='SHA256',checksumValue='0'*64)])])))
            receipt = dict(installer_sha256=catalog_tool.INSTALLER_SHA256,signature_status='Valid',signer_subject='Python Software Foundation',source_url=catalog_tool.INSTALLER_URL,version='3.14.10')
            with self.assertRaises(ValueError):
                catalog_tool.create_catalog(root, vendor, receipt, {'components':[]})
