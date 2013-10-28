from __future__ import unicode_literals

import json
import requests
import datetime

try:
    # Python 2
    from urllib import urlencode
except ImportError:
    # Python 3
    from urllib.parse import urlencode


class ShareaboutsEncoder (json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class ShareaboutsApiException (Exception):
    pass


class ShareaboutsApi (object):
    uri_templates = {
        'dataset_collection': r'{username}/datasets',
        'dataset_instance': r'{username}/datasets/{slug}',
        'place_collection': r'{username}/datasets/{dataset_slug}/places',
        'place_instance': r'{username}/datasets/{dataset_slug}/places/{pk}',
        'submission_collection': r'{username}/datasets/{dataset_slug}/places/{place_pk}/{type}',
        'submission_instance': r'{username}/datasets/{dataset_slug}/places/{place_pk}/{type}/{pk}',
        'all_submissions_collection': r'{username}/datasets/{dataset_slug}/{type}',
    }

    def __init__(self, root='/api/v1/'):
        self.uri_root = root

    def __str__(self):
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

    def send(self, method, url, data=None):
        if data is not None:
            data = json.dumps(data, cls=ShareaboutsEncoder)

        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}

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

        # Explicitly set the content length for delete
        if method == 'DELETE':
            headers.update({'Content-Length': '0'})

        response = requests.request(method, url, data=data, headers=headers)
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


# Models and Collections

class ShareaboutsModel (object):
    _pk_attr = 'id'
    _excluded_fields = ['id', 'created_datetime', 'updated_datetime']

    def __init__(self, api_proxy, collection=None, *args, **kwargs):
        self._api = api_proxy
        self._data = dict(*args, **kwargs)
        self.collection = collection

    def __str__(self):
        return "<%s %s %s>" % (self.__class__.__name__, self.get(self._pk_attr), self._data)

    def __repr__(self):
        return str(self)

    def api(self):
        return self._api

    def key(self):
        return self.get(self._pk_attr)

    def url(self):
        if 'url' in self:
            return self['url']
        elif self.collection and self._pk_attr in self:
            return '{0}/{1}'.format(self.collection.url(), self.key())
        else:
            raise ShareaboutsApiException(
                'Model {0} has no url attribute.'.format(self))

    def parse(self, raw_data):
        return raw_data

    def fetch(self, **options):
        api, url = self.api(), self.url()
        querystring = urlencode(options)
        raw_data = api._get_parsed_data('?'.join([url, querystring]))
        inst_data = self.parse(raw_data)
        self.clear()
        self.update(inst_data)
        return self

    def has_key(self):
        return self._pk_attr in self

    def save(self, new_data=None):
        api = self.api()

        send_data = self._data.copy()

        for field in self._excluded_fields:
            if field in send_data:
                del send_data[field]

        if new_data:
            send_data = send_data.copy()
            send_data.update(new_data)

        if self.has_key():
            response_data = api.send_and_parse('PUT', self.url(), send_data, [200])
        else:
            response_data = api.send_and_parse('POST', self.collection.url(), send_data, [201])

        self.update(response_data)

    # Dictionary interface
    def __getitem__(self, key): return self._data[key]
    def __setitem__(self, key, value): self._data[key] = value
    def __delitem__(self, key): del self._data[key]
    def __iter__(self): return iter(self._data)

    def get(self, key, default=None): return self._data.get(key, default)
    def clear(self): return self._data.clear()
    def update(self, other_data): return self._data.update(other_data)


class ShareaboutsCollection (object):
    _model_class = ShareaboutsModel

    def __init__(self, api_proxy, model_class=None, *args, **kwargs):
        self._api = api_proxy
        self._model_class = model_class or self._model_class
        self._data = data = list(*args, **kwargs)
        pk_attr = self._model_class._pk_attr
        ids = [inst_data[pk_attr]
               for inst_data in data
               if pk_attr in inst_data]
        self._data_by_id = dict(zip(ids, data))

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._data)

    def __repr__(self):
        return str(self)

    def api(self):
        return self._api

    def url(self):
        if hasattr(self, '_url'):
            return self._url
        else:
            raise ShareaboutsApiException(
                'Collection {0} has no _url attribute.'.format(self))

    def _make_inst(self, inst_data):
        Model = self._model_class
        inst = Model(self.api(), collection=self, **inst_data)
        return inst

    def _id_of(self, data):
        pk_attr = self._model_class._pk_attr
        return data.get(pk_attr, None)

    def parse(self, raw_data):
        return raw_data

    def fetch(self, **options):
        api, url = self.api(), self.url()
        querystring = urlencode(options)
        raw_data = api._get_parsed_data('?'.join([url, querystring]))
        collection_data = self.parse(raw_data)
        self.update(collection_data)
        return self

    def create(self, inst_data):
        inst = self._make_inst(inst_data)
        inst.save()
        self.add(inst_data)
        return inst

    # Dictionary-like interface
    def get(self, key, default=None):
        pk_attr = self._model_class._pk_attr
        inst_data = self._data_by_id.get(key, None)
        if inst_data is None:
            return default
        else:
            return self._make_inst(inst_data)

    # List-like interface
    def __getitem__(self, index):
        inst_data = self._data[index]
        return self._make_inst(inst_data)

    def __setitem__(self, index, value):
        self._data[index] = value

    def __iter__(self):
        return iter(self._make_inst(inst_data) for inst_data in self._data)

    # Set-like interface
    def __contains__(self, inst_data):
        inst_id = self._id_of(inst_data)
        return (inst_id in self._data_by_id)

    def add(self, inst_data):
        inst_id = self._id_of(inst_data)
        inst = self.get(inst_id)
        if inst:
            inst.update(inst_data)
        else:
            self._data.append(inst_data)
            if inst_id is not None:
                self._data_by_id[inst_id] = inst_data

    def update(self, collection_data):
        for inst_data in collection_data:
            self.add(inst_data)


class ShareaboutsAccount (ShareaboutsModel):
    _pk_attr = 'username'

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsAccount, self).__init__(api_proxy, *args, **kwargs)
        self.datasets = ShareaboutsDatasetSet(api_proxy, self)

    @property
    def username(self):
        return self.get('username')

    def dataset(self, dataset_slug):
        dataset = self.datasets.get(dataset_slug)
        if dataset is None:
            dataset = self.datasets._make_inst({'slug': dataset_slug})
        return dataset


class ShareaboutsDataset (ShareaboutsModel):
    _pk_attr = 'slug'

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsDataset, self).__init__(api_proxy, *args, **kwargs)
        self.places = ShareaboutsPlaceSet(api_proxy, self)
        self.submissions = ShareaboutsSubmissionSet(api_proxy, self)

    def __getattr__(self, submission_set_type):
        # Assume that unmatched attributes refer to a submission set
        return self.submissions.of_type(submission_set_type)


class ShareaboutsDatasetSet (ShareaboutsCollection):
    _model_class = ShareaboutsDataset

    def __init__(self, api_proxy, owner):
        super(ShareaboutsDatasetSet, self).__init__(api_proxy)
        self.owner = owner

    def _make_inst(self, inst_data):
        dataset = super(ShareaboutsDatasetSet, self)._make_inst(inst_data)
        dataset.owner = self.owner
        return dataset

    def url(self):
        return self.api().build_uri('dataset_collection', username=self.owner.username)


class ShareaboutsPlace (ShareaboutsModel):
    _excluded_fields = ShareaboutsModel._excluded_fields + ['dataset']

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsPlace, self).__init__(api_proxy, *args, **kwargs)
        self.submissions = ShareaboutsSubmissionSet(api_proxy, self)

    def __getattr__(self, submission_set_type):
        # Assume that unmatched attributes refer to a submission set
        return self.submissions.of_type(submission_set_type)

    def has_key(self):
        return 'id' in self

    def key(self):
        return self.get('id')


class ShareaboutsPlaceSet (ShareaboutsCollection):
    _model_class = ShareaboutsPlace

    def __init__(self, api_proxy, dataset):
        self.dataset = dataset
        super(ShareaboutsPlaceSet, self).__init__(api_proxy)

    def _make_inst(self, inst_data):
        inst = super(ShareaboutsPlaceSet, self)._make_inst(inst_data)
        inst.dataset = self.dataset
        return inst

    def url(self):
        return self.dataset.url() + '/places'


class ShareaboutsSubmission (ShareaboutsModel):
    _excluded_fields = ShareaboutsModel._excluded_fields + ['dataset']

    def has_key(self):
        return 'id' in self

    def key(self):
        return self.get('id')


class ShareaboutsSubmissionSet (ShareaboutsCollection):
    _model_class = ShareaboutsSubmission

    def __init__(self, api_proxy, place_or_dataset, type='submissions'):
        self.parent = place_or_dataset
        self.type = type
        super(ShareaboutsSubmissionSet, self).__init__(api_proxy)

    def of_type(self, type):
        return ShareaboutsSubmissionSet(self._api, self.parent, type)

    def url(self):
        return self.parent.url() + '/' + self.type
