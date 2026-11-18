import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))


class PreviewSystemDllTests(unittest.TestCase):
    def test_only_exact_os_compatibility_dlls_from_system32_are_removed(self):
        from preview_system_dlls import separate_os_prerequisites
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);system=root/'Windows'/'System32';system.mkdir(parents=True)
            pairs=[]
            for name in ('api-ms-win-core-console-l1-1-0.dll','ucrtbase.dll','VCRUNTIME140.dll','other.dll'):
                path=system/name;path.write_bytes(b'MZ'+name.encode());pairs.append((name,str(path),'BINARY'))
            kept,excluded=separate_os_prerequisites(pairs,root/'Windows')
            self.assertEqual([x[0] for x in kept],['VCRUNTIME140.dll','other.dll'])
            self.assertEqual([x['name'] for x in excluded],[x[0] for x in pairs[:2]])
            self.assertTrue(all(len(x['sha256'])==64 for x in excluded))
            self.assertNotIn(str(root),str(excluded))

    def test_non_system_source_is_recorded_without_fabricating_its_origin(self):
        from preview_system_dlls import separate_os_prerequisites
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'ucrtbase.dll';path.write_bytes(b'MZ')
            kept,excluded=separate_os_prerequisites([('ucrtbase.dll',str(path),'BINARY')],root/'Windows')
            self.assertEqual(kept,[])
            self.assertEqual(excluded[0]['origin'],'Outside System32; source directory not asserted')
            self.assertNotIn(str(root),str(excluded))


if __name__=='__main__':unittest.main()
