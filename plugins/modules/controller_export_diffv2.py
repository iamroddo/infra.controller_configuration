#!/usr/bin/python
# coding: utf-8 -*-
# (c) 2017, John Westcott IV <john.westcott.iv@redhat.com>
# based on the work of John Westcott
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


ANSIBLE_METADATA = {"metadata_version": "1.1", "status": ["preview"], "supported_by": "community"}


DOCUMENTATION = """
---
module: controller_export_diff
author: "Sean Sullivan (@sean-m-sullivan)"
short_description: Compare controller configuration resources with those defined in code.
description:
    - Compare controller configuration resources with those defined in code.
options:
    all:
      description:
        - Export all assets
      type: bool
      default: 'False'
    organizations:
      description:
        - organization names to export
      type: list
      elements: str
    users:
      description:
        - user names to export
      type: list
      elements: str
    teams:
      description:
        - team names to export
      type: list
      elements: str
    credential_types:
      description:
        - credential type names to export
      type: list
      elements: str
    credentials:
      description:
        - credential names to export
      type: list
      elements: str
    execution_environments:
      description:
        - execution environment names to export
      type: list
      elements: str
    notification_templates:
      description:
        - notification template names to export
      type: list
      elements: str
    inventory_sources:
      description:
        - inventory sources to export
      type: list
      elements: str
    inventory:
      description:
        - inventory names to export
      type: list
      elements: str
    projects:
      description:
        - project names to export
      type: list
      elements: str
    job_templates:
      description:
        - job template names to export
      type: list
      elements: str
    workflow_job_templates:
      description:
        - workflow names to export
      type: list
      elements: str
    applications:
      description:
        - OAuth2 application names to export
      type: list
      elements: str
    schedules:
      description:
        - schedule names to export
      type: list
      elements: str
    compare_items:
      description:
        - The dict of list objects to compare the api_list to.
        - This should match the dictionary name for the object above, and will be used for comparison.
      type: dict
      required: True
    set_absent:
      description:
        - Set state of items not in the compare list to 'absent'
      type: bool
      default: True
    with_present:
      description:
        - Include items in the original compare list in the output, and set state to 'present'
      type: bool
      default: True
    controller_host:
      description:
      - URL to your Automation Platform Controller instance.
      - If value not set, will try environment variable C(CONTROLLER_HOST) and then config files
      - If value not specified by any means, the value of C(127.0.0.1) will be used
      type: str
      aliases: [ tower_host ]
    controller_username:
      description:
      - Username for your controller instance.
      - If value not set, will try environment variable C(CONTROLLER_USERNAME) and then config files
      type: str
      aliases: [ tower_username ]
    controller_password:
      description:
      - Password for your controller instance.
      - If value not set, will try environment variable C(CONTROLLER_PASSWORD) and then config files
      type: str
      aliases: [ tower_password ]
    controller_oauthtoken:
      description:
      - The OAuth token to use.
      - This value can be in one of two formats.
      - A string which is the token itself. (i.e. bqV5txm97wqJqtkxlMkhQz0pKhRMMX)
      - A dictionary structure as returned by the token module.
      - If value not set, will try environment variable C(CONTROLLER_OAUTH_TOKEN) and then config files
      type: raw
      aliases: [ tower_oauthtoken ]
    validate_certs:
      description:
      - Whether to allow insecure connections to AWX.
      - If C(no), SSL certificates will not be validated.
      - This should only be used on personally controlled sites using self-signed certificates.
      - If value not set, will try environment variable C(CONTROLLER_VERIFY_SSL) and then config files
      type: bool
      aliases: [ tower_verify_ssl ]
    request_timeout:
      description:
      - Specify the timeout Ansible should use in requests to the controller host.
      - Defaults to 10s, but this is handled by the shared module_utils code
      - This option requires awx.awx>=22.7.0 or equivalent ansible.controller collection
      type: float
      version_added: "2.6.0"
    controller_config_file:
      description:
      - Path to the controller config file.
      - If provided, the other locations for config files will not be considered.
      type: path
      aliases: [tower_config_file]
requirements:
  - "awxkit >= 9.3.0"
  - awx.awx or ansible.controller collection
notes:
  - Specifying a name of "all" for any asset type will export all items of that asset type.
"""

EXAMPLES = """
- name: Get differential on projects and orgs.
  infra.controller_configuration.controller_export_diff:
    organizations: all
    projects: all
    compare_items:
      organizations:
        - name: Satellite
        - name: Default
      projects:
        - name: Test Project
          scm_type: git
          scm_url: https://github.com/ansible/tower-example.git
          scm_branch: master
          scm_clean: true
          description: Test Project 1
          organization: Default
          wait: true
          update_project: true
        - name: Test Inventory source project with credential
          scm_type: git
          scm_url: https://github.com/ansible/ansible-examples.git
          description: ansible-examples
          organization: Satellite
          scm_redential: gitlab-personal-access-token for satqe_auto_droid
          wait: false
    controller_host: https://controller
    controller_username: admin
    controller_password: secret123
    validate_certs: false
  register: export_results
...
"""

import logging
from ansible.module_utils.six.moves import StringIO
from copy import deepcopy

try:
    from ansible_collections.awx.awx.plugins.module_utils.awxkit import ControllerAWXKitModule
except ImportError:
    try:
        from ansible_collections.ansible.controller.plugins.module_utils.awxkit import ControllerAWXKitModule
    except ImportError:
        AAP_IMPORT_ERROR = True

try:
    from awxkit.api.pages.api import EXPORTABLE_RESOURCES

    HAS_EXPORTABLE_RESOURCES = True
except ImportError:
    HAS_EXPORTABLE_RESOURCES = False


def main():
    argument_spec = dict(
        all=dict(type="bool", default=False),
        applications=dict(type="list", elements="str"),
        credential_types=dict(type="list", elements="str"),
        credentials=dict(type="list", elements="str"),
        execution_environments=dict(type="list", elements="str"),
        inventory=dict(type="list", elements="str"),
        inventory_sources=dict(type="list", elements="str"),
        job_templates=dict(type="list", elements="str"),
        notification_templates=dict(type="list", elements="str"),
        organizations=dict(type="list", elements="str"),
        projects=dict(type="list", elements="str"),
        schedules=dict(type="list", elements="str"),
        teams=dict(type="list", elements="str"),
        users=dict(type="list", elements="str"),
        workflow_job_templates=dict(type="list", elements="str"),
        compare_items=dict(type="dict", required=True),
        set_absent=dict(type="bool", default=True),
        with_present=dict(type="bool", default=True),
    )

    module = ControllerAWXKitModule(argument_spec=argument_spec)

    if not HAS_EXPORTABLE_RESOURCES:
        module.fail_json(msg="Your version of awxkit does not have import/export")

    compare_items = module.params.get("compare_items")
    set_absent = module.params.get("set_absent")
    with_present = module.params.get("with_present")
    # The export process will never change the AWX system
    module.json_output["changed"] = False

    # The exporter code currently works like the following:
    #   Empty string == all assets of that type
    #   Non-Empty string = just one asset of that type (by name or ID)
    #   Asset type not present or None = skip asset type (unless everything is None, then export all)
    # Here we are going to setup a dict of values to export
    export_args = {}
    for resource in EXPORTABLE_RESOURCES:
        if module.params.get("all") or module.params.get(resource) == ["all"]:
            # If we are exporting everything or we got the keyword "all" we pass in an empty string for this asset type
            export_args[resource] = ""
        else:
            # Otherwise we take either the string or None (if the parameter was not passed) to get one or no items
            resource_param = module.params.get(resource)
            if resource_param is not None:
                export_args[resource] = module.params.get(resource)

    # Currently the export process does not return anything on error
    # It simply just logs to Python's logger
    # Set up a log gobbler to get error messages from export_assets
    log_capture_string = StringIO()
    ch = logging.StreamHandler(log_capture_string)
    for logger_name in ["awxkit.api.pages.api", "awxkit.api.pages.page"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        ch.setLevel(logging.ERROR)

    logger.addHandler(ch)
    log_contents = ""

    # Run the export process
    try:
        awxkit_list = module.get_api_v2_object().export_assets(**export_args)
        module.json_output["controller_objects"] = deepcopy(awxkit_list)
    except Exception as e:
        module.fail_json(msg="Failed to export assets {0}".format(e))
    finally:
        # Finally, consume the logs in case there were any errors and die if there were
        log_contents = log_capture_string.getvalue()
        log_capture_string.close()
        if log_contents != "":
            module.fail_json(msg=log_contents)

    # Loop over each resource type that we gathered from the API.
    output_list = {}
    for resource in export_args:
        try:
            if resource in compare_items:
                # Create a copy of the compare_items for this resource to avoid modifying the original
                compare_list = deepcopy(compare_items[resource])

                if with_present:
                    for resource_object in compare_list:
                        resource_object.update({"state": "present"})

                # Create a list to track items that should be removed from awxkit_list
                items_to_remove = []

                def items_match(compare_obj, api_obj):
                    """Return True if the compare_obj should be considered the same as api_obj.

                    Matching rules:
                    - 'name' must match
                    - if 'organization' is present in compare_obj, compare its name to api_obj.organization
                    - for any other key provided in compare_obj (description, scm_url, scm_credential, etc.)
                      compare the values. If the compare value is a dict, prefer its 'name' field.
                    - For scm_credential, accept either 'scm_credential' or 'credential' in the api object.
                    """

                    # Name must match
                    if compare_obj.get("name") != api_obj.get("name"):
                        return False

                    # Organization handling
                    if "organization" in compare_obj:
                        resource_org = compare_obj.get("organization")
                        api_org = api_obj.get("organization")

                        # normalize to names
                        if isinstance(resource_org, dict):
                            resource_org_name = resource_org.get("name")
                        else:
                            resource_org_name = resource_org

                        if isinstance(api_org, dict):
                            api_org_name = api_org.get("name")
                        else:
                            # api_org might be an ID or None, try summary_fields
                            api_org_name = api_org
                            if api_org is None or isinstance(api_org, int):
                                sf = api_obj.get("summary_fields", {})
                                sf_org = sf.get("organization") if isinstance(sf, dict) else None
                                if isinstance(sf_org, dict):
                                    api_org_name = sf_org.get("name")

                        if resource_org_name != api_org_name:
                            return False

                    # Other keys to compare if present in compare_obj
                    # Map compare keys to possible api keys
                    key_api_aliases = {
                        "scm_credential": ["scm_credential", "credential"],
                        # add other aliases here if needed
                    }

                    for key, val in compare_obj.items():
                        if key in ("name", "organization", "state"):
                            continue

                        # skip empty/None values in compare_obj
                        if val is None:
                            continue

                        # Determine api value(s) to compare against
                        api_keys = key_api_aliases.get(key, [key])
                        api_val = None
                        for ak in api_keys:
                            if ak in api_obj:
                                api_val = api_obj.get(ak)
                                break

                        # If api doesn't have the key, consider it a mismatch
                        if api_val is None:
                            return False

                        # If compare value is a dict, try to compare by name
                        if isinstance(val, dict):
                            val_to_cmp = val.get("name")
                        else:
                            val_to_cmp = val

                        if isinstance(api_val, dict):
                            api_val_to_cmp = api_val.get("name")
                        else:
                            api_val_to_cmp = api_val
                            # For credential keys, if api_val is an ID, try summary_fields
                            if key in ("scm_credential", "credential") and isinstance(api_val, int):
                                sf = api_obj.get("summary_fields", {})
                                sf_cred = sf.get("credential") if isinstance(sf, dict) else None
                                if isinstance(sf_cred, dict):
                                    api_val_to_cmp = sf_cred.get("name")

                        if val_to_cmp != api_val_to_cmp:
                            return False

                    return True

                def normalize_api_item(item):
                    """Normalize organization and credential fields in an API item.

                    This ensures downstream modules receive unambiguous organization names
                    and credential names rather than IDs or None values.
                    """
                    # Normalize organization to a name when possible
                    org = item.get("organization")
                    org_name = None

                    # If the API returned organization as dict -> take name
                    if isinstance(org, dict):
                        org_name = org.get("name")
                    else:
                        # If API returned an id or left org as numeric/None,
                        # try to get name from summary_fields.organization
                        sf = item.get("summary_fields", {})
                        sf_org = sf.get("organization") if isinstance(sf, dict) else None
                        if isinstance(sf_org, dict):
                            org_name = sf_org.get("name")

                    if org_name:
                        item["organization"] = org_name

                    # Normalize credentials: if there is a credential id but
                    # summary_fields.credential has name, set the credential field
                    # to that name for easier matching downstream.
                    # Consider both scm_credential and credential keys.
                    for cred_key in ("scm_credential", "credential"):
                        cred_val = item.get(cred_key)
                        if cred_val is None:
                            # try summary_fields
                            sf = item.get("summary_fields", {})
                            sf_cred = sf.get("credential") if isinstance(sf, dict) else None
                            if isinstance(sf_cred, dict) and sf_cred.get("name"):
                                # set both keys to the human-readable name
                                item[cred_key] = sf_cred.get("name")
                                # also set scm_credential for consistency
                                item.setdefault("scm_credential", sf_cred.get("name"))
                                break
                        else:
                            # If it's an object/dict, normalize to name
                            if isinstance(cred_val, dict) and cred_val.get("name"):
                                item[cred_key] = cred_val.get("name")

                for resource_object in compare_list:
                    for idx, api_item in enumerate(awxkit_list[resource]):
                        if idx in items_to_remove:
                            continue

                        # For users, compare by username only
                        if resource == "users":
                            if resource_object.get("username") == api_item.get("username"):
                                items_to_remove.append(idx)
                                break

                        else:
                            # Use flexible matching function that checks name and any provided fields
                            if items_match(resource_object, api_item):
                                items_to_remove.append(idx)
                                break

                # Remove matched items in reverse order to maintain indices
                for idx in sorted(items_to_remove, reverse=True):
                    awxkit_list[resource].pop(idx)

                # After looping through every item in the compare_items the remaining are set to absent.
                if set_absent:
                    if awxkit_list[resource]:
                        for remaining_item in awxkit_list[resource]:
                            # mark absent
                            remaining_item.update({"state": "absent"})
                            # normalize fields using helper
                            normalize_api_item(remaining_item)

                if with_present:
                    output_list[resource] = compare_list
                    if awxkit_list[resource]:
                        # normalize any remaining API items before adding to output
                        for api_item in awxkit_list[resource]:
                            normalize_api_item(api_item)
                        output_list[resource].extend(awxkit_list[resource])
                else:
                    # normalize all API items before adding to output
                    for api_item in awxkit_list[resource]:
                        normalize_api_item(api_item)
                    output_list[resource] = awxkit_list[resource]
            else:
                # Resource not in compare_items, but was exported
                if set_absent and awxkit_list.get(resource):
                    for item in awxkit_list[resource]:
                        item.update({"state": "absent"})
                        normalize_api_item(item)
                    output_list[resource] = awxkit_list[resource]

        except Exception as e:
            module.fail_json(msg="Failed to process resource {0}: {1}".format(resource, str(e)))
    # Post-process output_list to detect ambiguous name+organization entries
    # and attach an identifier to make downstream selection unambiguous.
    for resource, items in list(output_list.items()):
        # Build a map of (name, organization) -> list of items
        name_org_map = {}
        for itm in items:
            name = itm.get("name")
            org = itm.get("organization")
            key = (name, org)
            name_org_map.setdefault(key, []).append(itm)

        # Mark ambiguous keys and attach an identifier
        for key, grouped in name_org_map.items():
            if len(grouped) > 1:
                # ambiguous across orgs or duplicates — mark all
                for g in grouped:
                    g["ambiguous"] = True
                    # prefer id when present
                    if g.get("id"):
                        g["identifier"] = str(g.get("id"))
                    else:
                        # fallback to name|org string
                        g["identifier"] = "{0}|{1}".format(g.get("name"), g.get("organization"))
            else:
                g = grouped[0]
                g["ambiguous"] = False
                if g.get("id"):
                    g["identifier"] = str(g.get("id"))
                else:
                    g["identifier"] = "{0}|{1}".format(g.get("name"), g.get("organization"))

    module.json_output["difference"] = output_list
    module.exit_json(**module.json_output)


if __name__ == "__main__":
    main()
