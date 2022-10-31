# SPDX-License-Identifier: MIT
#
# Copyright (c) 2022 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import logging
import re
from reml.project import Project, Version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Babeltrace1Project(Project):
    def __init__(self) -> None:
        self._name = "Babeltrace1"
        self._changelog_project_name = "babeltrace"
        super().__init__()

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        try:
            tokenized_version = series.split(".")
            if len(tokenized_version) != 2:
                return False
            if int(tokenized_version[0]) != 1:
                return False

            return True
        except:
            # Any error is the result of an unexpected release series format anyhow.
            return False

    def _ci_release_job_name(self, version):
        series = "{}.{}".format(version.major, version.minor)
        return "babeltrace_v{}_release".format(series)

    def _update_version(self, new_version: Version) -> None:
        with open(self._repo_base_path + "/configure.ac", "r") as original:
            original_contents = original.read()

        new_version_string = "{major}.{minor}.{patch}".format(
            major=new_version.major, minor=new_version.minor, patch=new_version.patch
        )

        # Replace version in the AC_INIT(...) line
        new_contents = re.sub(
            r"^(AC_INIT\(\[babeltrace],\[)([^]]*)(],.*)$",
            "\g<1>{new_version}\g<3>".format(new_version=new_version_string),
            original_contents,
            flags=re.MULTILINE,
        )

        with open(self._repo_base_path + "/configure.ac", "w") as new:
            new.write(new_contents)

    def _commit_and_tag(self, new_version: Version) -> None:
        commit_msg = "Update version to v{major}.{minor}.{patch}".format(
            major=new_version.major, minor=new_version.minor, patch=new_version.patch
        )
        self._repo.git.add("ChangeLog")
        self._repo.git.commit("-s", "-m" + commit_msg)
        self._repo.git.tag(
            "-s",
            "v{}".format(str(new_version)),
            "-m Version {}".format(str(new_version)),
        )

        new_version = Version(
            new_version.major, new_version.minor, new_version.patch + 1
        )
