from __future__ import unicode_literals, division

import json
import math
import requests
import datetime
from shareabouts.exceptions import ShareaboutsApiException

try:
    # Python 2
    from urllib import urlencode
except ImportError:
    # Python 3
    from urllib.parse import urlencode


class ShareaboutsModel (object):
    _pk_attr = 'id'
    _excluded_fields = ['id', 'url', 'created_datetime', 'updated_datetime']

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
            collection_url = self.collection.url()
            if collection_url.endswith('/'):
                return ''.join([collection_url, self.key()])
            else:
                return '/'.join([collection_url, self.key()])
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

    def is_new(self):
        return self._pk_attr not in self
    
    def has_key(self):
        return self._pk_attr in self

    def serialize(self):
        return self._data

    def save(self):
        api = self.api()

        send_data = self.serialize().copy()

        for field in self._excluded_fields:
            if field in send_data:
                del send_data[field]

        if self.has_key():
            response_data = api.send_and_parse('PUT', self.url(), send_data, [200])
        else:
            response_data = api.send_and_parse('POST', self.collection.url(), send_data, [201])

        self.update(response_data)

    def destroy(self):
        if not self.is_new():
            response = api.send('DELETE', self.url())
            
        if self.collection is not None:
            self.collection.remove(self)
            self.collection = None

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
    _metadata_attr = 'metadata'
    _results_attr = 'results'

    def __init__(self, api_proxy, model_class=None, *args, **kwargs):
        self._api = api_proxy
        self._model_class = model_class or self._model_class
        self._data = []
        self._data_by_id = {}

        self.update(list(*args, **kwargs))

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

    def parse_page_count(self, raw_data):
        assert self._metadata_attr in raw_data
        assert self._results_attr in raw_data

        metadata = raw_data[self._metadata_attr]

        # If this is not the last page, then calculate page count based on the
        # number of results on this page.
        if metadata['next'] and len(raw_data[self._results_attr]) > 0:
            self.page_count = int(math.ceil(raw_data[self._metadata_attr].get('length') / len(raw_data[self._results_attr])))

        # If this is the last page, but there is no previous page, then this
        # is the first of one page.
        elif not metadata['previous']:
            self.page_count = 1

        # Otherwise we're on the last page and we can just set the page count
        # to the current page number
        else:
            self.page_count = raw_data[self._metadata_attr].get('page')

    def parse(self, raw_data):
        self.parse_page_count(raw_data)
        return raw_data[self._results_attr]

    def fetch(self, url=None, **options):
        api, url = self.api(), url or self.url()
        querystring = urlencode(options)
        if '?' not in url:
            full_url = '?'.join([url, querystring])
        else:
            full_url = '&'.join([url, querystring])

        raw_data = api._get_parsed_data(full_url)
        collection_data = self.parse(raw_data)
        self.update(collection_data)
        return raw_data

    def fetch_all(self, url=None, **options):
        page_url = url or self.url()

        while page_url:
            page_data = self.fetch(url=page_url, **options)
            yield page_data
            page_url = page_data[self._metadata_attr].get('next')

    def create(self, inst_data):
        inst = self._make_inst(inst_data)
        inst.save()
        self.add(inst)
        return inst

    def serialize(self):
        return [inst.serialize() for inst in self]

    # Dictionary-like interface
    def get(self, key, default=None):
        try:
            return self._data_by_id[key]
        except KeyError:
            if isinstance(default, dict):
                return self._make_inst(default)
            else:
                return default

    # List-like interface
    def __getitem__(self, index):
        return self._data[index]

    def __setitem__(self, index, value):
        self._data[index] = value

    def __iter__(self):
        return iter(self._data)

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
            inst = self._make_inst(inst_data)
            self._data.append(inst)
            if inst_id is not None:
                self._data_by_id[inst_id] = inst
                # NOTE: When the instance's id changes, we need to notice.
        return inst

    def update(self, collection_data):
        for inst_data in collection_data:
            self.add(inst_data)
    
    def remove(self, inst):
        # TODO: implement removal.
        pass


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
            dataset = self.datasets.add({'slug': dataset_slug})
        return dataset


class ShareaboutsAccountSet (ShareaboutsCollection):
    _model_class = ShareaboutsAccount

    def __init__(self, api_proxy, *args, **kwargs):
        self._url = api_proxy.uri_root
        super(ShareaboutsAccountSet, self).__init__(api_proxy, *args, **kwargs)


class ShareaboutsDataset (ShareaboutsModel):
    _pk_attr = 'slug'

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsDataset, self).__init__(api_proxy, *args, **kwargs)
        self.places = ShareaboutsPlaceSet(api_proxy, self)
        self.submissions = ShareaboutsSubmissionSet(api_proxy, self)

    @property
    def submission_sets(self):
        try:
            return self.submissions.sets.values()
        except AttributeError:
            return []

    def serialize(self):
        data = super(ShareaboutsDataset, self).serialize()
        try:
            data['submission_sets'] = {
                sset.name: sset.serialize()
                for sset in self.submission_sets
            }
        except AttributeError:
            data['submission_sets'] = {}
        return data

    def __getattr__(self, submission_set_name):
        # Assume that unmatched attributes refer to a submission set
        return self.submissions.in_set(submission_set_name)

    def is_new(self):
        # Even new datasets have a slug, so we check something else
        return 'created_datetime' not in self


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
        return self.owner.url() + '/datasets'


def geojson_method(fname):
    def conditional_method(self, key, *args, **kwargs):
        if key in ('geometry', 'id'):
            f = getattr(self._data, fname)
        else:
            f = getattr(self._data['properties'], fname)
        return f(key, *args, **kwargs)
    return conditional_method

class ShareaboutsPlace (ShareaboutsModel):
    _excluded_fields = ShareaboutsModel._excluded_fields + ['dataset', 'attachments', 'submissions', 'id']

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsPlace, self).__init__(api_proxy, *args, **kwargs)
        self.submissions = ShareaboutsSubmissionSet(api_proxy, self)

    def __getattr__(self, submission_set_name):
        # Assume that unmatched attributes refer to a submission set
        return self.submissions.in_set(submission_set_name)

    def has_key(self):
        return 'id' in self

    def key(self):
        return self.get('id')

    # Dictionary interface
    __getitem__ = geojson_method('__getitem__')
    __setitem__ = geojson_method('__setitem__')
    get = geojson_method('get')

    def __iter__(self):
        for key in self._data:
            if key in ('geometry', 'id'):
                yield key
        for key in self._data['properties']:
            if key not in ('geometry', 'id'):
                yield key


class ShareaboutsPlaceSet (ShareaboutsCollection):
    _model_class = ShareaboutsPlace
    _results_attr = 'features'

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
    _excluded_fields = ShareaboutsModel._excluded_fields + ['place', 'attachments', 'id']

    def has_key(self):
        return 'id' in self

    def key(self):
        return self.get('id')


class ShareaboutsSubmissionSet (ShareaboutsCollection):
    _model_class = ShareaboutsSubmission

    def __init__(self, api_proxy, place_or_dataset, set_name='submissions'):
        self.parent = place_or_dataset
        self.name = set_name
        super(ShareaboutsSubmissionSet, self).__init__(api_proxy)

    def in_set(self, set_name):
        try:
            return self.sets[set_name]

        # If it doesn't have a _sets attribute, set it.
        except AttributeError:
            self.sets = {set_name: ShareaboutsSubmissionSet(self._api, self.parent, set_name)}
            return self.sets[set_name]

        # If it has a _sets attribute, but no set_name key, set it.
        except KeyError:
            self.sets[set_name] = ShareaboutsSubmissionSet(self._api, self.parent, set_name)
            return self.sets[set_name]

    def url(self):
        return self.parent.url() + '/' + self.name
