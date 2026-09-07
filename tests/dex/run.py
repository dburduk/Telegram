"""Run production Java routing/key logic with small Android-free test doubles."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
ui = root / 'TMessagesProj/src/main/java/org/telegram/ui'

def method(path, signature):
    text = path.read_text(encoding='utf-8')
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

source = (Path(__file__).parent / 'Regression.java.in').read_text()
source = source.replace('/* ROUTING */', method(ui / 'LaunchActivity.java', 'public boolean needPresentFragment('))
source = source.replace('/* ESCAPE */', method(ui / 'PhotoViewer.java', 'private boolean handleEscapeKey('))
for signature in ('public boolean dispatchKeyEvent(', 'public boolean dispatchKeyEventPreIme('):
    assert 'if (handleEscapeKey(event))' in method(ui / 'PhotoViewer.java', signature)
launch = (ui / 'LaunchActivity.java').read_text()
assert launch.count('(!AndroidUtilities.isInMultiwindow || getResources().getConfiguration().screenWidthDp >= 840)') == 3
java_home = os.environ.get('JAVA_HOME')
def tool(name):
    return str(Path(java_home) / 'bin' / name) if java_home else name
with tempfile.TemporaryDirectory() as temp:
    java = Path(temp) / 'Regression.java'
    java.write_text(source)
    subprocess.run([tool('javac'), str(java)], check=True)
    subprocess.run([tool('java'), '-cp', temp, 'Regression'], check=True)
