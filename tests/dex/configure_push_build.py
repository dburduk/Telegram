"""Inject private client configuration for the fork build; never print credentials."""
import json
import os
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
required = ('DEX_GOOGLE_SERVICES_JSON', 'DEX_TELEGRAM_API_ID', 'DEX_TELEGRAM_API_HASH')
missing = [name for name in required if not os.environ.get(name)]
if missing:
    raise SystemExit('Missing build configuration: ' + ', '.join(missing))

firebase = json.loads(os.environ['DEX_GOOGLE_SERVICES_JSON'])
if 'private_key' in firebase or firebase.get('type') == 'service_account':
    raise SystemExit('Use Android client google-services.json, never a server service-account key')
if firebase.get('project_info', {}).get('project_id') != 'dex-messenger-test':
    raise SystemExit('Unexpected Firebase project for this test build')
clients = firebase.get('client', [])
if not any(c.get('client_info', {}).get('android_client_info', {}).get('package_name') == 'org.telegram.messenger.beta' for c in clients):
    raise SystemExit('Missing beta Android client configuration')
api_id = os.environ['DEX_TELEGRAM_API_ID']
api_hash = os.environ['DEX_TELEGRAM_API_HASH']
if not api_id.isdecimal() or int(api_id) <= 0 or not re.fullmatch(r'[0-9a-fA-F]{32}', api_hash):
    raise SystemExit('Invalid Telegram API client configuration')

build_vars = root / 'TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java'
text = build_vars.read_text()
text, ids = re.subn(r'public static int APP_ID = [^;]+;', 'public static int APP_ID = ' + api_id + ';', text)
text, hashes = re.subn(r'public static String APP_HASH = [^;]+;', 'public static String APP_HASH = "' + api_hash + '";', text)
if ids != 1 or hashes != 1:
    raise SystemExit('Telegram API declarations changed; refusing incomplete configuration')
for module in ('TMessagesProj', 'TMessagesProj_App'):
    (root / module / 'google-services.json').write_text(json.dumps(firebase, indent=2) + '\n')
build_vars.write_text(text)
print('Configured beta client with the fork Firebase project and Telegram API identity')
