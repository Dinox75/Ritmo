"""Keep Windows 10+ OS compatibility stubs out of a Windows-only preview."""
import hashlib
from pathlib import Path, PureWindowsPath


def separate_os_prerequisites(binaries, windows_root):
    system=(Path(windows_root)/'System32').resolve()
    kept=[];excluded=[]
    for item in binaries:
        destination,source,kind=item
        name=PureWindowsPath(destination).name
        low=name.casefold()
        if kind=='BINARY' and (low=='ucrtbase.dll' or (low.startswith('api-ms-win-') and low.endswith('.dll'))):
            actual=Path(source).resolve()
            if not actual.is_file():
                raise ValueError('Collected compatibility DLL is not a readable file')
            with actual.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            # Exclusion does not trust or execute the collected bytes. API-set
            # contracts/UCRT are supplied by the minimum supported OS, regardless
            # of whether the compiler collected a stub from System32 or elsewhere.
            # Keep that distinction instead of claiming an unobserved origin.
            origin='Windows/System32' if actual.is_relative_to(system) else 'Outside System32; source directory not asserted'
            excluded.append(dict(name=name,sha256=digest,origin=origin,
                                 disposition='Not redistributed; supplied by supported Windows 10/11 x64 operating system'))
        else:kept.append(item)
    return kept,excluded
