# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import re
import git
import glob
import tempfile
import shutil
import subprocess
import jenkinsapi
import requests
import time
import hashlib
import os
from enum import Enum
from click import style, echo, confirm, progressbar
from datetime import date
from typing import Optional
import reml.config


class ReleaseType(Enum):
    STABLE = 1
    RELEASE_CANDIDATE = 2


class InvalidReleaseSeriesError(Exception):
    def __init__(self) -> None:
        super().__init__()


class InvalidReleaseTypeError(Exception):
    def __init__(self) -> None:
        super().__init__()


class UnexpectedTagNameError(Exception):
    def __init__(self) -> None:
        super().__init__()


class AbortedRelease(Exception):
    def __init__(self) -> None:
        super().__init__()


class Version:
    def __init__(self, major: int, minor: int, patch: int, rc: Optional[int]) -> None:
        self._major = major
        self._minor = minor
        self._patch = patch
        self._rc = rc

    def __str__(self) -> str:
        version_string = "{}.{}.{}".format(self._major, self._minor, self._patch)
        if self._rc:
            version_string = version_string + "-rc" + str(self._rc)
        return version_string

    @property
    def major(self) -> int:
        return self._major

    @property
    def minor(self) -> int:
        return self._minor

    @property
    def patch(self) -> int:
        return self._patch

    @property
    def rc(self) -> Optional[int]:
        return self._rc


class ReleaseDescriptor:
    def __init__(self, project_name: str, version: Version, path: str) -> None:
        self._project_name = project_name
        self._version = version
        self._path = path

    @property
    def name(self) -> str:
        return "{} {}".format(self._project_name, str(self._version))

    @property
    def version(self) -> Version:
        return self._version

    @property
    def path(self) -> str:
        return self._path


class ReleaseArtifact:
    def __init__(self, name: str, url: str) -> None:
        self._name = name
        self._url = url
        self._dir = tempfile.mkdtemp()

        echo(
            style("Fetching ")
            + style(self._name, fg="white", bold=True)
            + style("..."),
            nl=False,
        )
        remote = requests.get(self._url)
        artifact_path = os.path.join(self._dir, self._name)
        with open(artifact_path, "wb") as new_file:
            new_file.write(remote.content)
        echo(style("✓", fg="green", bold=True))

        echo(
            style("Hashing ") + style(self._name, fg="white", bold=True) + style("..."),
            nl=False,
        )
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        with open(artifact_path, "rb") as tarball:
            content = tarball.read()
            md5.update(content)
            sha1.update(content)
            sha256.update(content)

        with open(artifact_path + ".md5", "w") as md5file:
            md5file.write("{}  {}\n".format(md5.hexdigest(), self._name))

        with open(artifact_path + ".sha1", "w") as sha1file:
            sha1file.write("{}  {}\n".format(sha1.hexdigest(), self._name))

        with open(artifact_path + ".sha256", "w") as sha256file:
            sha256file.write("{}  {}\n".format(sha256.hexdigest(), self._name))
        echo(style("✓", fg="green", bold=True))

        echo(
            style("Signing ") + style(self._name, fg="white", bold=True) + style("..."),
            nl=False,
        )
        subprocess.call(["gpg", "--armor", "-b", artifact_path])
        echo(style("✓", fg="green", bold=True))

    def upload(self, location: str) -> None:
        echo(
            style("Uploading artifacts... "),
            nl=False,
        )
        for filename in os.listdir(self._dir):
            if not filename.startswith(self._name):
                continue
            path = os.path.join(self._dir, filename)
            subprocess.call(["rsync", path, location + "/"])
        echo(style("✓", fg="green", bold=True))


class Project:
    def __init__(self) -> None:
        self._repo = None
        self._workdir = tempfile.mkdtemp()
        self._repo_base_path = None
        self._config = reml.config.get_project_config(self.name)

        try:
            self._git_urls = self._config["git_urls"]
            if isinstance(self._git_urls, str):
                self._git_urls = [self._git_urls]
            self._ci_url = self._config["ci_url"]
            self._ci_user = self._config["ci_user"]
            self._ci_token = self._config["ci_token"]
            self._upload_location = self._config["upload_location"]
        except KeyError as e:
            raise reml.config.MissingConfigurationAttributeError(self.name, e.args[0])

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        raise NotImplementedError()

    @staticmethod
    def _branch_name_from_series(series: str) -> str:
        return "stable-" + series

    @staticmethod
    def _version_from_tag(tag_name: str) -> Version:
        exp = re.compile(r"v(\d*)\.(\d*)\.(\d*)")
        exp_rc = re.compile(r"v(\d*)\.(\d*)\.(\d*)-rc(\d*)")
        rc = None

        if exp.match(tag_name):
            major, minor, patch = exp.match(tag_name).groups()
        else:
            if exp_rc.match(tag_name) is None:
                raise UnexpectedTagNameError()
            else:
                major, minor, patch, rc = exp_rc.match(tag_name).groups()
        major = int(major)
        minor = int(minor)
        patch = int(patch)
        rc = None if rc is None else int(rc)
        return Version(major, minor, patch, rc)

    @staticmethod
    def _version_from_series(series: str) -> Version:
        exp = re.compile(r"(\d*)\.(\d*)")

        if exp.match(series):
            major, minor = exp.match(series).groups()
        else:
            raise InvalidReleaseSeriesError()

        return Version(major, minor, 0, None)

    @staticmethod
    def _tag_from_version(version: Version) -> str:
        return "v" + str(version)

    def _ci_release_job_name(self, version):
        series = "{}.{}".format(version.major, version.minor)
        branch_name = self._branch_name_from_series(series)
        return "{}-{}-release".format(self.name.lower(), branch_name)

    def _update_version(self, new_version: Version) -> None:
        raise NotImplementedError()

    def _commit_and_tag(self, new_version: Version) -> None:
        raise NotImplementedError()

    def _clone_repo(self) -> None:
        echo("Cloning upstream {} repository... ".format(self.name), nl=False)
        git.Git(self._workdir).clone(self._git_urls[0])
        self._repo_base_path = glob.glob(self._workdir + "/*/")[0]
        self._repo = git.Repo(self._repo_base_path)
        echo(style("✓", fg="green", bold=True))

        for git_url in self._git_urls[1:]:
            self._repo.git.remote("set-url", "--add", "origin", git_url)

    def _branch_exists(self, branch_name: str) -> bool:
        for ref in self._repo.refs:
            if ref.name == ("origin/" + branch_name):
                return True
        return False

    def _set_current_branch(self, branch_name: str, create_branch: bool) -> None:
        if create_branch:
            echo("Switching to new branch " + branch_name)
            self._repo.git.checkout("-b", branch_name)
        else:
            echo("Switching to branch " + branch_name)
            self._repo.git.checkout(branch_name)

    def _latest_tag_name(self) -> str:
        return self._repo.git.describe("--abbrev=0")

    def _update_changelog(self, new_version: Version, tagline: str):
        echo("Updating ChangeLog... ".format(self.name), nl=False)
        latest_tag_name = self._latest_tag_name()
        for ref in self._repo.refs:
            if ref.name == latest_tag_name:
                latest_tag_sha = ref.commit.hexsha
                break

        today = date.today()

        title = "{}-{:02d}-{:02d} {} {}".format(
            today.year, today.month, today.day, self.name.lower(), str(new_version)
        )
        if tagline:
            title = title + " ({})".format(tagline)
        title = title + "\n"

        changelog_new_section = [title]
        for commit in self._repo.iter_commits():
            if commit.hexsha == latest_tag_sha:
                break
            entry = "\t* {}\n".format(commit.summary)
            changelog_new_section.append(entry)

        with open(self._repo_base_path + "/ChangeLog", "r") as original:
            contents = original.read()
        with open(self._repo_base_path + "/ChangeLog", "w") as modified:
            for entry in changelog_new_section:
                modified.write(entry)
            modified.write("\n")
            modified.write(contents)
        echo(style("✓", fg="green", bold=True))

    def _publish(self, branch_name: str) -> None:
        echo("Pushing new release... ".format(self.name), nl=False)
        self._repo.git.push("origin", branch_name + ":" + branch_name, "--tags")
        echo(style("✓", fg="green", bold=True))

    def _generate_artifact(self, version: Version) -> str:
        job_name = self._ci_release_job_name(version)
        server = jenkinsapi.jenkins.Jenkins(self._ci_url, self._ci_user, self._ci_token)
        job = server.create_job(job_name, None)

        echo(
            style("Launching build job ")
            + style(job_name, fg="white", bold=True)
            + style("... "),
            nl=False,
        )
        queue_item = job.invoke()
        echo(style("✓", fg="green", bold=True))

        echo(
            style("Waiting for job ")
            + style(job_name, fg="white", bold=True)
            + style(" to be scheduled... "),
            nl=False,
        )
        while True:
            try:
                queue_item.poll()
                build = queue_item.get_build()
                break
            except jenkinsapi.custom_exceptions.NotBuiltYet:
                time.sleep(1)
                continue
        echo(style("✓", fg="green", bold=True))

        estimated_duration_secs = int(build.get_estimated_duration())

        delay_secs = 10
        with progressbar(
            length=estimated_duration_secs,
            show_eta=True,
            label="Building on " + build.get_slave(),
        ) as progress:
            while build.is_running():
                time.sleep(delay_secs)
                progress.update(delay_secs)

        build_status = build.poll()
        if build_status["result"] != "SUCCESS":
            echo(style("Build failed 🤯", fg="red", bold=True))
            raise AbortedRelease()

        if len(build.get_artifact_dict()) != 1:
            echo(
                style(
                    "Unexpected artifacts generated by the release job 🤯",
                    fg="red",
                    bold=True,
                )
            )
            echo("Artifacts: " + str(build.get_artifact_dict()))
            raise AbortedRelease()

        echo(
            style("Getting artifact URL... "), nl=False,
        )
        artifact = next(iter(build.get_artifacts()))
        echo(style(artifact.url, fg="white", bold=True))
        return ReleaseArtifact(artifact.filename, artifact.url)

    def release(
        self, series: str, tagline: str, dry: bool, release_type: ReleaseType
    ) -> str:
        if not self._is_release_series_valid(series):
            raise InvalidReleaseSeriesError()

        self._clone_repo()

        branch_name = self._branch_name_from_series(series)
        branch_exists = self._branch_exists(branch_name)

        if not branch_exists:
            echo(
                "Branch "
                + style(branch_name, fg="white", bold=True)
                + " does not exist"
            )
            if release_type != ReleaseType.RELEASE_CANDIDATE:
                raise InvalidReleaseTypeError()

            new_version = self._version_from_series(series)
            new_version = Version(new_version.major, new_version.minor, 0, 1)
        else:
            echo(
                "Branch "
                + style(branch_name, fg="white", bold=True)
                + " already exists"
            )
            self._set_current_branch(branch_name, False)
            latest_tag_name = self._latest_tag_name()
            latest_version = self._version_from_tag(latest_tag_name)
            major = latest_version.major
            if release_type is ReleaseType.RELEASE_CANDIDATE:
                minor = latest_version.minor
                patch = 0
                rc = latest_version.rc + 1
            else:
                minor = latest_version.minor
                patch = latest_version.patch + 1
                rc = None

            new_version = Version(major, minor, patch, rc)
            echo(
                style("Updating version from ")
                + style(str(latest_version), fg="white", bold=True)
                + style(" to ")
                + style(str(new_version), fg="white", bold=True)
            )

        self._update_changelog(new_version, tagline)
        self._update_version(new_version)
        self._commit_and_tag(new_version)

        if not branch_exists:
            self._set_current_branch(branch_name, True)

        if (
            confirm(
                style("Publish tree at ")
                + style(self._repo_base_path, fg="white", bold=True)
                + style(" ?")
            )
            and not dry
        ):
            self._publish(branch_name)
        else:
            raise AbortedRelease()

        artifact = self._generate_artifact(new_version)
        artifact.upload(self._upload_location)

        return ReleaseDescriptor(self.name, new_version, self._repo_base_path)
