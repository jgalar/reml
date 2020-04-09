# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import logging

from reml.project import Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BabeltraceProject(Project):
    def __init__(self) -> None:
        self._name = "Babeltrace"
        self._git_url = "https://github.com/efficios/babeltrace.git"
        super().__init__()

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        return False
