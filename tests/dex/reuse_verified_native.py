"""Reuse unchanged native code from the pinned, previously tested diagnostic APK."""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

reference = Path(sys.argv[1])
destination = Path(sys.argv[2])
expected = '10499ccc3ce58660e1fdc0c19c00d4df52abb3209b4b1c31d010ed0d13cb69ad'
if hashlib.sha256(reference.read_bytes()).hexdigest() != expected:
    raise SystemExit('Reference APK checksum mismatch')
subprocess.run(['git', 'diff', '--quiet', '1ebd418cb98ae69c446adacd166af752fae31b34', 'HEAD', '--',
    'TMessagesProj/jni', 'TMessagesProj/src/main/java', 'build.gradle', 'gradle.properties', 'gradle/wrapper'], check=True)
abis = {'armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64'}
with zipfile.ZipFile(reference) as apk:
    if len(sys.argv) > 3:
        with zipfile.ZipFile(sys.argv[3]) as output:
            old = {n: hashlib.sha256(apk.read(n)).digest() for n in apk.namelist() if n.startswith('lib/') and n.endswith('.so')}
            new = {n: hashlib.sha256(output.read(n)).digest() for n in output.namelist() if n.startswith('lib/') and n.endswith('.so')}
            if old != new:
                raise SystemExit('Native libraries differ from the verified reference APK')
            print('Verified all APK native libraries match the tested reference byte for byte')
    else:
        for abi in sorted(abis):
            name = 'lib/' + abi + '/libtmessages.49.so'
            target = destination / abi / 'libtmessages.49.so'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(apk.read(name))
        print('Prepared verified native libraries for all four ABIs')
