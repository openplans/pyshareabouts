import json
import requests
import datetime
from .exceptions import ShareaboutsApiException
from .models import ShareaboutsAccount


class ShareaboutsEncoder (json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class ShareaboutsApi (object):
    uri_templates = {
        'dataset_collection': r'{username}/datasets/',
        'dataset_instance': r'{username}/datasets/{slug}/',
        'keys_collection': r'{username}/datasets/{dataset_slug}/keys/',
        'place_collection': r'{username}/datasets/{dataset_slug}/places/',
        'place_instance': r'{username}/datasets/{dataset_slug}/places/{pk}/',
        'submission_collection': r'{username}/datasets/{dataset_slug}/places/{place_pk}/{type}/',
        'submission_instance': r'{username}/datasets/{dataset_slug}/places/{place_pk}/{type}/{pk}/',
        'all_submissions_collection': r'{username}/datasets/{dataset_slug}/{type}/',
    }

    def __init__(self, root='/api/v1/'):
        self.uri_root = root

    def __unicode__(self):
        return '<Shareabouts API object with root "{0}">'.format(self.uri_root)

    def build_uri(self, name, *args, **kwargs):
        uri_template = self.uri_templates[name]
        uri_path = uri_template.format(*args, **kwargs)
        return (self.uri_root + uri_path)

    def authenticate_with_django_request(self, request):
        self.authenticate_with_csrf_token(request.META.get('CSRF_COOKIE', ''),
                                          request.META.get('HTTP_COOKIE', ''))

    def authenticate_with_csrf_token(self, token, cookies):
        self.csrf_token = token
        self.cookies = cookies

    def authenticate_with_key(self, key):
        self.key = key
    
    def authenticate_with_basic(self, username, password):
        self.auth = (username, password)

    def send(self, method, url, data=None):
        if data is not None:
            data = json.dumps(data, cls=ShareaboutsEncoder)

        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}
        auth = None

        # Set authentication headers
        if hasattr(self, 'csrf_token') and hasattr(self, 'cookies'):
            headers.update({
                'Cookie': self.cookies,
                'X-CSRFToken': self.csrf_token
            })

        if hasattr(self, 'key'):
            headers.update({
                'X-Shareabouts-Key': self.key
            })
        
        if hasattr(self, 'auth'):
            auth = self.auth

        # Explicitly set the content length for delete
        if method == 'DELETE':
            headers.update({'Content-Length': '0'})

        response = requests.request(method, url, 
                                    data=data, headers=headers, auth=auth)
        return response

    def get(self, url, default=None):
        """
        Returns decoded data from a GET request, or default on non-200
        responses.
        """
        res = self.send('GET', url)
        res_json = res.text
        return (json.loads(res_json) if res.status_code == 200 else default)

    def send_and_parse(self, method, url, data=None, valid=[200]):
        response = self.send(method, url, data)
        if response.status_code in valid:
            fetched_data = json.loads(response.text)
            return fetched_data
        else:
            raise ShareaboutsApiException((
                  'Did not get a valid response from {0}. Instead, got a {1} '
                  'with the text "{2}".'
                ).format(url, response.status_code, response.text))

    def _get_parsed_data(self, url):
        fetched_data = self.send_and_parse('GET', url)
        return fetched_data

    def account(self, account_username):
        owner = ShareaboutsAccount(self, username=account_username)
        return owner
