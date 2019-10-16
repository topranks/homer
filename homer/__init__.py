"""Homer package."""
import logging
import os
import pathlib
import sys

from collections import defaultdict
from typing import Callable, DefaultDict, Dict, List, Mapping, Tuple

import pynetbox

from pkg_resources import DistributionNotFound, get_distribution

from homer.config import HierarchicalConfig, load_yaml_config
from homer.devices import Device, Devices
from homer.exceptions import HomerError
from homer.netbox import NetboxData
from homer.templates import Renderer
from homer.transports.junos import connected_device


try:
    __version__ = get_distribution('homer').version  # Must be the same used as 'name' in setup.py
    """:py:class:`str`: the version of the current Homer package."""
except DistributionNotFound:  # pragma: no cover - this should never happen during tests
    pass  # package is not installed

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Homer:
    """The instance to run Homer."""

    OUT_EXTENSION = '.out'
    """:py:class:`str`: the extension for the generated output files."""

    def __init__(self, main_config: Mapping):
        """Initialize the instance.

        Arguments:
            main_config (dict): the configuration dictionary.

        """
        logger.debug('Initialized with configuration: %s', main_config)
        self._main_config = main_config
        private_base_path = self._main_config['base_paths'].get('private', '')
        self._config = HierarchicalConfig(
            self._main_config['base_paths']['public'], private_base_path=private_base_path)

        devices_config = load_yaml_config(
            os.path.join(self._main_config['base_paths']['public'], 'config', 'devices.yaml'))
        private_devices_config = {}  # type: dict
        if private_base_path:
            private_devices_config = load_yaml_config(
                os.path.join(private_base_path, 'config', 'devices.yaml'))

        self._netbox_api = None
        if self._main_config.get('netbox', None) is not None:
            self._netbox_api = pynetbox.api(
                self._main_config['netbox']['url'], token=self._main_config['netbox']['token'])

        self._devices = Devices(devices_config, private_devices_config)
        self._renderer = Renderer(self._main_config['base_paths']['public'])
        self._output_base_path = pathlib.Path(self._main_config['base_paths']['output'])

    def generate(self, query: str) -> int:
        """Generate the configuration only saving it locally, no remote action is performed.

        Arguments:
            query (str): the query to select the devices.

        Return:
            int: ``0`` on success, a small positive integer on failure.

        """
        logger.info('Generating configuration for query %s', query)
        self._prepare_out_dir()
        successes, _ = self._execute(self._device_generate, query)
        return Homer._parse_results(successes)

    def diff(self, query: str) -> int:
        """Generate the configuration and check the diff with the current live one.

        Arguments:
            query (str): the query to select the devices.

        Return:
            int: ``0`` on success, a small positive integer on failure.

        """
        logger.info('Generating diff for query %s', query)
        successes, diffs = self._execute(self._device_diff, query)
        for diff, diff_devices in diffs.items():
            print('Diff for {n} devices: {devices}'.format(n=len(diff_devices), devices=diff_devices))
            print(diff)
            print('---------------')

        return Homer._parse_results(successes)

    def commit(self, query: str, *, message: str = '-') -> int:
        """Commit the generated configuration asking for confirmation.

        Arguments:
            query (str): the query to select the devices.
            message (str): the commit message to use.

        Return:
            int: ``0`` on success, a small positive integer on failure.

        """
        logger.info('Committing config for query %s with message: %s', query, message)
        successes, _ = self._execute(self._device_commit, query, message=message)
        return Homer._parse_results(successes)

    def _device_generate(self, device: Device, device_config: str) -> Tuple[bool, str]:
        """Save the generated configuration in a local file.

        Arguments:
            device (homer.devices.Device): the device instance.
            device_config (str): the generated configuration for the device.

        Returns:
            tuple: a two-element tuple with a boolean as first parameter that represent the success of the operation
            or not and a second element with a string that is not used but is required by the callback API.

        """
        output_path = self._output_base_path / '{fqdn}{out}'.format(fqdn=device.fqdn, out=Homer.OUT_EXTENSION)
        with open(str(output_path), 'w') as f:
            f.write(device_config)
            logger.info('Written configuration for %s in %s', device.fqdn, output_path)

        return True, ''

    def _device_diff(self, device: Device, device_config: str) -> Tuple[bool, str]:  # pylint: disable=no-self-use
        """Perform a configuration diff between the generated configuration and the live one.

        Arguments:
            device (homer.devices.Device): the device instance.
            device_config (str): the generated configuration for the device.

        Returns:
            tuple: a two-element tuple with a boolean as first parameter that represent the success of the operation
            or not and a second element with a string that contains the configuration differences.

        """
        with connected_device(device.fqdn) as connection:
            return connection.commit_check(device_config)

    def _device_commit(self, device: Device, device_config: str, *,  # pylint: disable=no-self-use
                       message: str = '-') -> Tuple[bool, str]:
        """Commit a new configuration to the device.

        Arguments:
            device (homer.devices.Device): the device instance.
            device_config (str): the generated configuration for the device.
            message (str): the commit message to use.

        Returns:
            tuple: a two-element tuple with a boolean as first parameter that represent the success of the operation
            or not and a second element with a string that contains the configuration differences.

        """
        def callback(fqdn: str, diff: str) -> None:
            """Callback as required by :py:class:`homer.transports.junos.ConnectedDevice.commit`."""
            if not sys.stdout.isatty():
                raise HomerError('Not in a TTY, unable to ask for confirmation')

            print('Configuration diff for {fqdn}:\n{diff}'.format(fqdn=fqdn, diff=diff))
            print('Type "yes" to commit, "no" to abort.')

            for _ in range(2):
                resp = input('> ')
                if resp == 'yes':
                    break
                elif resp == 'no':
                    raise HomerError('Commit aborted')
                else:
                    print(('Invalid response, please type "yes" to commit or "no" to abort. After 2 wrong answers the '
                           'commit will be aborted.'))
            else:
                raise HomerError('Too many invalid answers, commit aborted')

        with connected_device(device.fqdn) as connection:
            try:
                connection.commit(device_config, message, callback)
                return True, ''
            except HomerError:
                logger.exception('Failed to commit on %s', device.fqdn)
                return False, ''

    def _prepare_out_dir(self) -> None:
        """Prepare the out directory creating the directory if doesn't exists and deleting any pre-generated file."""
        self._output_base_path.mkdir(parents=True, exist_ok=True)
        for path in self._output_base_path.iterdir():
            if path.is_file() and path.suffix == Homer.OUT_EXTENSION:
                path.unlink()

    def _execute(self, callback: Callable, query: str, **kwargs: str) -> Tuple[Dict, DefaultDict]:
        """Execute Homer based on the given action and query.

        Arguments:
            callback (Callable): the callback to call for each device.
            query (str): the query to filter the devices to act on.
            **kwargs (str): any additional keyword argument to pass to the callback

        Returns:
            tuple: a two-element tuple, with the first item as a dictionary that contains two keys (:py:data:`True`
            and :py:data:`False`) and as value a list of device FQDN that were successful (True) or failed (False)
            the operation and a second element a :py:class:`collections.defaultdict` that has as keys the
            configuration differences and as values the list of device FQDN that reported that diff.

        """
        diffs = defaultdict(list)  # type: defaultdict
        successes = {True: [], False: []}  # type: dict
        for device in self._devices.query(query):
            logger.info('Generating configuration for %s', device.fqdn)

            try:
                device_data = self._config.get(device)
                if self._netbox_api is not None:
                    device_data['netbox'] = NetboxData(self._netbox_api, device)
                device_config = self._renderer.render(device.role, device_data)
            except HomerError:
                logger.exception('Device %s failed to render the template, skipping.', device.fqdn)
                successes[False].append(device.fqdn)
                continue

            device_success, device_diff = callback(device, device_config, **kwargs)
            successes[device_success].append(device.fqdn)
            diffs[device_diff].append(device.fqdn)

        return successes, diffs

    @staticmethod
    def _parse_results(successes: Mapping[bool, List[Device]]) -> int:
        """Parse the results dictionary, log and return the approriate exit status code.

        Arguments:
            successes (dict): a dictionary that contains two keys (:py:data:`True` and :py:data:`False`) and as value
                a list of device FQDN that were successful (True) or failed (False) the operation.

        Return:
            int: ``0`` on success, a small positive integer on failure.

        """
        if successes[False]:
            logger.error('Homer run had issues on %d devices: %s', len(successes[False]), successes[False])
            return 1

        logger.info('Homer run completed successfully on %d devices: %s', len(successes[True]), successes[True])
        return 0
