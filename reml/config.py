# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import configparser
import os
import click


class MissingConfigurationError(Exception):
    def __init__(self, expected_path: str) -> None:
        self._expected_path = expected_path
        super().__init__()

    @property
    def expected_path(self) -> str:
        return self._expected_path


class MissingConfigurationAttributeError(Exception):
    def __init__(self, project_name: str, attribute: str) -> None:
        self._project_name = project_name
        self._attribute = attribute
        super().__init__()

    @property
    def attribute(self) -> str:
        return self._attribute

    @property
    def project_name(self) -> str:
        return self._project_name


def get_project_config(project_name: str) -> dict:
    cfg_path = os.path.join(click.get_app_dir("reml"), "reml.conf")
    parser = configparser.RawConfigParser()
    read_files = parser.read([cfg_path])
    if len(read_files) == 0:
        raise MissingConfigurationError(cfg_path)

    project_section = None

    for section in parser.sections():
        if section.lower() == project_name.lower():
            project_section = section
            break

    if not project_section:
        return None
    else:
        project_cfg = {}
        for key, val in parser[project_section].items():
            vals = val.split(",")
            if len(vals) == 1:
                project_cfg[key] = val
            else:
                project_cfg[key] = vals
        return project_cfg
