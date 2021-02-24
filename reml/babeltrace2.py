# SPDX-License-Identifier: MIT
#
# Copyright (c) 2021 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import logging
import re
from reml.project import Project, Version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Babeltrace2Project(Project):
    def __init__(self) -> None:
        self._name = "Babeltrace2"
        self._changelog_project_name = "Babeltrace"
        super().__init__()

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        try:
            tokenized_version = series.split(".")
            if len(tokenized_version) != 2:
                return False
            if int(tokenized_version[0]) != 2:
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

        new_contents = re.sub(
            r"^m4_define\(\[bt_version_major\],.*\)$",
            "m4_define([bt_version_major], [{}])".format(new_version.major),
            original_contents,
            flags=re.MULTILINE,
        )
        new_contents = re.sub(
            r"^m4_define\(\[bt_version_minor\],.*\)$",
            "m4_define([bt_version_minor], [{}])".format(new_version.minor),
            new_contents,
            flags=re.MULTILINE,
        )
        new_contents = re.sub(
            r"^m4_define\(\[bt_version_patch\],.*\)$",
            "m4_define([bt_version_patch], [{}])".format(new_version.patch),
            new_contents,
            flags=re.MULTILINE,
        )

        with open(self._repo_base_path + "/configure.ac", "w") as new:
            new.write(new_contents)

    def _get_release_name(self) -> str:
        with open(self._repo_base_path + "/configure.ac", "r") as original:
            contents = original.read()

        return re.search(
            r"^m4_define\(\[bt_version_name\], \[(.*)\]\)*$",
            contents,
            flags=re.MULTILINE,
        ).group(1)

    def _commit_and_tag(self, new_version: Version) -> None:
        release_name = self._get_release_name()
        commit_msg = 'Release: Babeltrace {}.{}.{} "{}"'.format(
            new_version.major, new_version.minor, new_version.patch, release_name
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
        commit_msg = "Update working version to Babeltrace v{}".format(str(new_version))
        self._update_version(new_version)
        self._repo.git.add("configure.ac")
        self._repo.git.commit("-s", "-m" + commit_msg)
