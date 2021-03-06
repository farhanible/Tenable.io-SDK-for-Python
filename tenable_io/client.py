import requests
import sys

from requests.packages.urllib3 import Retry
from requests.utils import quote

from tenable_io.config import TenableIOConfig
from tenable_io.exceptions import TenableIOApiException
from tenable_io.api.agents import AgentsApi
from tenable_io.api.agent_groups import AgentGroupsApi
from tenable_io.api.base import BaseRequest
from tenable_io.api.editor import EditorApi
from tenable_io.api.exclusions import ExclusionApi
from tenable_io.api.file import FileApi
from tenable_io.api.folders import FoldersApi
from tenable_io.api.groups import GroupsApi
from tenable_io.api.plugins import PluginsApi
from tenable_io.api.policies import PoliciesApi
from tenable_io.api.scans import ScansApi
from tenable_io.api.scanners import ScannersApi
from tenable_io.api.server import ServerApi
from tenable_io.api.session import SessionApi
from tenable_io.api.target_groups import TargetGroupsApi
from tenable_io.api.users import UsersApi
from tenable_io.api.workbenches import WorkbenchApi
from tenable_io.helpers.folder import FolderHelper
from tenable_io.helpers.policy import PolicyHelper
from tenable_io.helpers.scan import ScanHelper
from tenable_io.log import format_request, logging


class TenableIOClient(object):

    _MAX_RETRIES = 3
    _RETRY_STATUS_CODES = {429, 501, 502, 503, 504}

    def __init__(
            self,
            access_key=TenableIOConfig.get('access_key'),
            secret_key=TenableIOConfig.get('secret_key'),
            endpoint=TenableIOConfig.get('endpoint'),
            impersonate=None,
    ):
        self._access_key = access_key
        self._secret_key = secret_key
        self._endpoint = endpoint
        self._impersonate = impersonate

        self._init_session()
        self._init_api()
        self._init_helpers()

    def _init_session(self):
        """
        Initializes the requests session
        """
        retries = Retry(
                    total=TenableIOClient._MAX_RETRIES,
                    status_forcelist=TenableIOClient._RETRY_STATUS_CODES,
                    backoff_factor=0.1,
                    respect_retry_after_header=True
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        self._session = requests.Session()
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        self._session.headers.update({
            u'X-ApiKeys': u'accessKey=%s; secretKey=%s;' % (self._access_key, self._secret_key),
            u'User-Agent': u'TenableIOSDK Python/%s' % ('.'.join([str(i) for i in sys.version_info][0:3]))
        })
        if self._impersonate:
            self._session.headers.update({
                u'X-Impersonate': u'username=%s' % self._impersonate
            })

    def _init_api(self):
        """
        Initializes all api.
        """
        self.agents_api = AgentsApi(self)
        self.agent_groups_api = AgentGroupsApi(self)
        self.editor_api = EditorApi(self)
        self.exclusions_api = ExclusionApi(self)
        self.file_api = FileApi(self)
        self.folders_api = FoldersApi(self)
        self.groups_api = GroupsApi(self)
        self.plugins_api = PluginsApi(self)
        self.policies_api = PoliciesApi(self)
        self.scans_api = ScansApi(self)
        self.scanners_api = ScannersApi(self)
        self.server_api = ServerApi(self)
        self.session_api = SessionApi(self)
        self.target_groups_api = TargetGroupsApi(self)
        self.users_api = UsersApi(self)
        self.workbenches_api = WorkbenchApi(self)

    def _init_helpers(self):
        """
        Initializes all helpers.
        """
        self.folder_helper = FolderHelper(self)
        self.policy_helper = PolicyHelper(self)
        self.scan_helper = ScanHelper(self)

    def _error_handler(f):
        """
        Decorator to handle response error.
        :param f: Response returning method.
        :return: A Response returning method that raises TenableIOException for error in response.
        """
        def wrapper(*args, **kwargs):
            response = f(*args, **kwargs)
            if not 200 <= response.status_code <= 299:
                raise TenableIOApiException(response)
            return response
        return wrapper

    @staticmethod
    def impersonate(username):
        return TenableIOClient(impersonate=username)

    @_error_handler
    def get(self, uri, path_params=None, **kwargs):
        return self._request('GET', uri, path_params, **kwargs)

    @_error_handler
    def post(self, uri, payload=None, path_params=None, **kwargs):
        if isinstance(payload, BaseRequest):
            payload = payload.as_payload()
        return self._request('POST', uri, path_params, json=payload, **kwargs)

    @_error_handler
    def put(self, uri, payload=None, path_params=None, **kwargs):
        if isinstance(payload, BaseRequest):
            payload = payload.as_payload()
        return self._request('PUT', uri, path_params, json=payload, **kwargs)

    @_error_handler
    def delete(self, uri, path_params=None, **kwargs):
        return self._request('DELETE', uri, path_params, **kwargs)

    def _request(self, method, uri, path_params=None, **kwargs):
        if path_params:
            # Ensure path param is encoded.
            path_params = {key: quote(str(value), safe=u'') for key, value in path_params.items()}
            uri %= path_params

        full_uri = self._endpoint + uri

        response = self._session.request(method, full_uri, **kwargs)
        log_message = format_request(response)

        logging.info(log_message)
        if not 200 <= response.status_code <= 299:
            logging.error(log_message)

        return response

    # Delayed qualifying decorator as staticmethod. This is a workaround to error raised from using a decorator
    # decorated by @staticmethod.
    _error_handler = staticmethod(_error_handler)
