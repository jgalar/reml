# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

from reml.project import Project


class LTTngToolsProject(Project):
    def __init__(self, branch: str, tagline: str):
        self._branch = branch
