import urllib
from .exceptions import ShareaboutsApiException


class ShareaboutsModel (object):
    _pk_attr = 'id'
    _excluded_fields = ['id', 'url', 'created_datetime', 'updated_datetime']

    def __init__(self, api_proxy, collection=None, *args, **kwargs):
        self._api = api_proxy
        self._data = dict(*args, **kwargs)
        self.collection = collection

    def __unicode__(self):
        return "<%s %s %s>" % (self.__class__.__name__, self.get(self._pk_attr), self._data)

    def __repr__(self):
        return unicode(self)

    def api(self):
        return self._api

    def key(self):
        return self.get(self._pk_attr)

    def url(self):
        if 'url' in self:
            return self['url']
        elif self.collection and self._pk_attr in self:
            return '{0}{1}/'.format(self.collection.url(), self.key(), '/')
        else:
            raise ShareaboutsApiException(
                'Model {0} has no url attribute.'.format(self))

    def fetch(self):
        api, url = self.api(), self.url()
        querystring = urllib.urlencode(options)
        fetched_data = api._get_parsed_data('?'.join([url, querystring]))
        self.clear()
        self.update(fetched_data)
        return self

    def is_new(self):
        return self._pk_attr not in self
    
    def mutable_data(self):
        data = self._data.copy()
        for field in self._excluded_fields:
            if field in data:
                del data[field]
        return data

    def save(self, new_data=None):
        api = self.api()
        data_to_send = self.mutable_data()

        if new_data:
            data_to_send = data_to_send.copy()
            data_to_send.update(new_data)

        if not self.is_new():
            response_data = api.send_and_parse('PUT', self.url(), data_to_send, [200])
        else:
            response_data = api.send_and_parse('POST', self.collection.url(), data_to_send, [201])

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

    def __init__(self, api_proxy, model_class=None, *args, **kwargs):
        self._api = api_proxy
        self._model_class = model_class or self._model_class
        self._data = data = list(*args, **kwargs)
        pk_attr = self._model_class._pk_attr
        ids = [inst_data[pk_attr]
               for inst_data in data
               if pk_attr in inst_data]
        self._data_by_id = dict(zip(ids, data))

    def __unicode__(self):
        return "<%s %s>" % (self.__class__.__name__, self._data)

    def __repr__(self):
        return unicode(self)

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

    def fetch(self, **options):
        api, url = self.api(), self.url()
        querystring = urllib.urlencode(options)
        collection_data = api._get_parsed_data('?'.join([url, querystring]))
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
        if isinstance(inst_data, basestring):
            inst_id = inst_data
        else:
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
        return self.api().build_uri('dataset_collection', username=self.owner.username)


class ShareaboutsPlace (ShareaboutsModel):
    _excluded_fields = ShareaboutsModel._excluded_fields + ['dataset', 'attachments', 'submissions', 'id']

    def __init__(self, api_proxy, *args, **kwargs):
        super(ShareaboutsPlace, self).__init__(api_proxy, *args, **kwargs)
        self.submissions = ShareaboutsSubmissionSet(api_proxy, self)

    def __getattr__(self, submission_set_type):
        # Assume that unmatched attributes refer to a submission set
        return self.submissions.of_type(submission_set_type)


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
        return self.dataset.url() + 'places/'


class ShareaboutsSubmission (ShareaboutsModel):
    _excluded_fields = ShareaboutsModel._excluded_fields + ['place', 'attachments', 'type', 'id']


class ShareaboutsSubmissionSet (ShareaboutsCollection):
    _model_class = ShareaboutsSubmission

    def __init__(self, api_proxy, place_or_dataset, type='submissions'):
        self.parent = place_or_dataset
        self.type = type
        super(ShareaboutsSubmissionSet, self).__init__(api_proxy)

    def of_type(self, type):
        return ShareaboutsSubmissionSet(self._api, self.parent, type)

    def url(self):
        return self.parent.url() + self.type + '/'
