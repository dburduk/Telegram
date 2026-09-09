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
source = source.replace('/* SPLIT_WIDTH */', method(ui.parent / 'messenger/AndroidUtilities.java', 'public static int getTabletLeftFragmentSize('))
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
    diagnostic_source = '''public class DiagnosticCases {
    /* SANITIZE */
    /* DESCRIBE */
    static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) {
        String key = "AIza" + "k".repeat(35);
        String token = "t".repeat(150);
        String safe = sanitize("FIS_AUTH_ERROR " + key + " " + token + " https://example.com/private?token=secret");
        check(safe.contains("FIS_AUTH_ERROR"));
        check(!safe.contains(key) && !safe.contains(token) && !safe.contains("secret"));
        String error = describe(new java.io.IOException("SERVICE_NOT_AVAILABLE", new IllegalStateException("FIS_AUTH_ERROR")));
        check(error.contains("IOException") && error.contains("SERVICE_NOT_AVAILABLE") && error.contains("FIS_AUTH_ERROR"));
        check(!describe(null).isEmpty());
        check(sanitize("word ".repeat(500)).length() <= 1000);
        check(!sanitize("line1\\nline2").contains("\\n"));
        System.out.println("PASS: push diagnostic error details and redaction");
    }
}'''
    diagnostics = ui.parent / 'messenger/PushDiagnostics.java'
    diagnostic_source = diagnostic_source.replace('/* SANITIZE */', method(diagnostics, 'public static String sanitize('))
    diagnostic_source = diagnostic_source.replace('/* DESCRIBE */', method(diagnostics, 'public static String describe('))
    java = Path(temp) / 'DiagnosticCases.java'
    java.write_text(diagnostic_source)
    subprocess.run([tool('javac'), str(java)], check=True)
    subprocess.run([tool('java'), '-cp', temp, 'DiagnosticCases'], check=True)
