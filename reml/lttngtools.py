# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import logging
import re
from reml.project import Project, Version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LTTngToolsProject(Project):
    def __init__(self) -> None:
        self._name = "LTTng-tools"
        self._git_url = "git@git.lttng.org:lttng-tools.git"
        super().__init__()

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        return True

    def _update_version(self, new_version: Version) -> None:
        with open(self._repo_base_path + "/configure.ac", "r") as original:
            contents = original.read()
        exp = re.compile(r"AC_INIT.*")
        span = exp.search(contents).span()

        with open(self._repo_base_path + "/configure.ac", "w") as new:
            new.write(contents[0 : span[0]])
            new.write(
                "AC_INIT([lttng-tools],[{}],[jeremie.galarneau@efficios.com],[],[https://lttng.org])".format(
                    str(new_version)
                )
            )
            new.write(contents[span[1] :])

    def _commit_and_tag(self, new_version: Version) -> None:
        commit_msg = "Update version to v{}".format(str(new_version))
        self._repo.git.add("ChangeLog", "configure.ac")
        self._repo.git.commit("-s", "-m" + commit_msg)
        self._repo.git.tag(
            "-s",
            "v{}".format(str(new_version)),
            "-m Version {}".format(str(new_version)),
        )
