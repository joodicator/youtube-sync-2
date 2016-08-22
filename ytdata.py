import sys
import os.path

import apiclient.discovery

API_KEY_FILE = os.path.join(os.path.dirname(__file__), 'ytdata-api-key') 

def build_service(api_key=None):
    if api_key is None and os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            api_key = file.read().strip()
    elif api_key is None:
        print('Warning: %s does not exist, but it should contain a YouTube'
            ' Data API key (see https://developers.google.com/youtube/'
            'registering_an_application). Proceeding with no API key.\n'
            % API_KEY_FILE, file=sys.stderr)
    return apiclient.discovery.build(
        serviceName  = 'youtube',
        version      = 'v3',
        developerKey = api_key)
