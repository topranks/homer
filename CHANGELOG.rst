Homer Changelog
---------------


`v0.2.3`_ (2020-06-11)
^^^^^^^^^^^^^^^^^^^^^^

Minor improvements
""""""""""""""""""

* Improve error catching (`T253795`_).

  * For the diff action catch all the errors directly in the transport in order to return a consistent success and
    diff result for each device, skipping as a result those with failure. In case of failure return ``None`` so that
    it can be distinguished from an empty diff and reported as such both in logging and in the output.
  * For the commit action let the exceptions raise in the transport and be catched and logged in the main ``Homer``
    class with the same effective result that any failing device is skipped without interrupting the whole run.
  * In both cases log also the traceback when the debug logging is enabled.

`v0.2.2`_ (2020-05-06)
^^^^^^^^^^^^^^^^^^^^^^

Bug Fixes
"""""""""

* netbox: adapt to new Netbox API

  * Netbox API starting with Netbox 2.8.0 have removed the choices API endpoint. Adapt the handling of the device
    status accordingly.


`v0.2.1`_ (2020-04-30)
^^^^^^^^^^^^^^^^^^^^^^

Minor improvements
""""""""""""""""""

* Add Python 3.8 support
* transports.junos: do not commit check on empty diff:

  * When performing a commit check, do not actually run the ``commit_check`` on the device if there is no diff.
  * In all cases perform a rollback, even on empty diff.

`v0.2.0`_ (2020-04-06)
^^^^^^^^^^^^^^^^^^^^^^

New features
""""""""""""

* Handle commit abort separately (`T244362`_).

  * Introduce a new ``HomerAbortError`` exception to specifically handle cases in which the user explicitely aborted
    a write operation.
  * In the commit callback raise an ``HomerAbortError`` exception when the user abort the commit or reach the limit of
    invalid replies.

* transports.junos: retry when a timeout occurs during commits (`T244363`_).
* transports.junos: handle timeouts separately (`T244363`_).

  * Handle the ``RpcTimeoutError`` junos exception separately to avoid to have a full stacktrace in the logs as it's a
    normal failure scenario.
  * Handle the ``TimeoutExpiredError`` ncclient exception separately to avoid failures when calling ``close()``.

* allow overriding the ``ssh_config`` path in homer's config.
* plugins: initial implementation for Netbox data.

  * Allow to specify via configuration a Python module to load as a plugin for the Netbox data gathering.
  * When configured the plugin class is dynamically loaded and exposed to the templates as netbox.device_plugin.
  * It is basically the same implementation of ``NetboxDeviceData`` but allows for any specific selection of data from
    Netbox that is not generic enough to be included in Homer itself.

* commit: do not ``commit_check`` on initial empty diff.

  * As a consequence of commit ``1edb7c2`` if a device have an empty diff and a commit is run on it, it will run a
    ``commit_check`` anyway. Avoid this situation skipping the whole operation if at the first attempt the diff is
    empty.
  * In case of enough timeouts that don't allow Homer to complete the commit operation within the same run, the
    automatic rollback should be waited before retrying, otherwise the device will just be skipped.
  * To achieve this, passing the attempt number to all the operation callbacks, also if it's currently only used in
    the commit one to keep the same interface for all of them.

* diff: allow to omit the actual diff.

  * Add the ``-o/--omit-diff`` option to the ``diff`` sub-command to allow to omit the actual diff for security reasons
    if the diff results will be used for monitoring/alarming purposes, as the diff might contain sensitive data.

* diff: use different exit code if there is a diff (`T249224`_).

  * To allow to run automatic checks on outstanding diffs between the devices running configuration and the one defined
    in Homer's config and templates, make the diff command to return a different exit code when successfull but there
    is any diff.
  * In case of failure the failure exit code will prevail.

* netbox: silently skip devices without platform.

  * Some devices might not be reachable by default because not managed. Allow to more silently skip those (debug level
    logging only) if they are missing both the FQDN and the Platform in Netbox.

Minor improvements
""""""""""""""""""

* Sort deviced by FQDN
* netbox: skip virtual chassis devices without a domain field set, as they would not be reachable.

Miscellanea
"""""""""""

* examples: add comments to example config
* config: complete test coverage
* doc: fix example ``config.yaml`` indentation
* gitignore: add ``/plugins`` to gitignore to be able to link a plugin directory from other locations in a local
  checkout.

`v0.1.1`_ (2019-12-17)
^^^^^^^^^^^^^^^^^^^^^^

* Make the transport username configurable


`v0.1.0`_ (2019-12-17)
^^^^^^^^^^^^^^^^^^^^^^

* First release (`T228388`_).


.. _`T228388`: https://phabricator.wikimedia.org/T228388
.. _`T244362`: https://phabricator.wikimedia.org/T244362
.. _`T244363`: https://phabricator.wikimedia.org/T244363
.. _`T249224`: https://phabricator.wikimedia.org/T249224
.. _`T253795`: https://phabricator.wikimedia.org/T253795

.. _`v0.1.0`: https://github.com/wikimedia/operations-software-homer/releases/tag/v0.1.0
.. _`v0.1.1`: https://github.com/wikimedia/operations-software-homer/releases/tag/v0.1.1
.. _`v0.2.0`: https://github.com/wikimedia/operations-software-homer/releases/tag/v0.2.0
.. _`v0.2.1`: https://github.com/wikimedia/homer/releases/tag/v0.2.1
.. _`v0.2.2`: https://github.com/wikimedia/homer/releases/tag/v0.2.2
.. _`v0.2.3`: https://github.com/wikimedia/homer/releases/tag/v0.2.3
