# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import re

import git
import glob
import mimetypes
import tempfile
import shutil
import subprocess
import jenkinsapi
import requests
import time
import urllib
import hashlib
import os
from enum import Enum
from click import style, echo, confirm, progressbar
from datetime import date
from typing import Optional, List
import reml.config

import github3


def _run_cmd_confirm_on_failure(args: List[str]) -> None:
    run_cmd = True

    while run_cmd:
        try:
            subprocess.check_call(args)
            return
        except subprocess.CalledProcessError as e:
            run_cmd = confirm(
                style("💣 Failed to run ", bold=True, fg="red")
                + "'{}' (returned {})".format(" ".join(args), e.returncode),
                default=True,
                show_default=True,
            )


class ReleaseType(Enum):
    STABLE = 1
    RELEASE_CANDIDATE = 2


class InvalidReleaseSeriesError(Exception):
    def __init__(self) -> None:
        super().__init__()


class InvalidReleaseTypeError(Exception):
    def __init__(self) -> None:
        super().__init__()


class InvalidReleaseRebuildOptionError(Exception):
    def __init__(self) -> None:
        super().__init__()


class UnexpectedTagNameError(Exception):
    def __init__(self) -> None:
        super().__init__()


class AbortedRelease(Exception):
    def __init__(self) -> None:
        super().__init__()


class Version:
    def __init__(
        self, major: int, minor: int, patch: int, rc: Optional[int] = None
    ) -> None:
        self._major = major
        self._minor = minor
        self._patch = patch
        self._rc = rc

    def __str__(self) -> str:
        version_string = "{}.{}.{}".format(self._major, self._minor, self._patch)
        if self._rc:
            version_string = version_string + "-rc" + str(self._rc)
        return version_string

    def series(self) -> str:
        return "{}.{}".format(self._major, self._minor)

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
    def __init__(self, artifact: jenkinsapi.artifact.Artifact, no_sign: bool) -> None:
        self._name = artifact.filename
        self._dir = tempfile.mkdtemp()

        echo(
            style("Fetching ")
            + style(self._name, fg="white", bold=True)
            + style("..."),
            nl=False,
        )
        artifact_path = os.path.join(self._dir, self._name)
        artifact.save_to_dir(self._dir)
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

        if not no_sign:
            echo(
                style("Signing ")
                + style(self._name, fg="white", bold=True)
                + style("..."),
                nl=False,
            )
            _run_cmd_confirm_on_failure(["gpg", "--armor", "-b", artifact_path])
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
            _run_cmd_confirm_on_failure(["rsync", path, location + "/"])
        echo(style("✓", fg="green", bold=True))

    def upload_to_github(
        self, gh: github3.repos.repo.Repository, urls: list[str], tag: str
    ):
        echo(style("Uploading artifacts to GitHub... "), nl=False)
        mimetypes.init()
        releases = []
        for url in urls:
            owner, repo_name = url.split(":")[1].split("/")
            repo = gh.repository(owner, repo_name.rstrip(".git"))
            release = repo.release_from_tag(tag)
            if not release:
                echo(
                    style(
                        "😱 Couldn't find release by tag `{}` at {}".format(
                            repo.html_url, tag
                        ),
                        bold=True,
                        fd="red",
                    )
                )
                continue
            releases.append(release)

        for filename in os.listdir(self._dir):
            if not filename.startswith(self._name):
                continue
            path = os.path.join(self._dir, filename)
            content_type = mimetypes.guess_type(path)[0]
            with open(path, "rb") as f:
                for release in releases:
                    for asset in release.assets():
                        if asset.name == filename:
                            asset.delete()
                    release.upload_asset(
                        (
                            content_type
                            if content_type is not None
                            else "application/octet-stream"
                        ),
                        filename,
                        f,
                    )
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
            self._github_user = self._config["github_user"]
            self._github_token = self._config["github_token"]
            self._upload_location = self._config["upload_location"]
        except KeyError as e:
            raise reml.config.MissingConfigurationAttributeError(self.name, e.args[0])

    @property
    def name(self) -> str:
        return self._name

    @property
    def changelog_project_name(self) -> str:
        return getattr(self, "_changelog_project_name", self.name)

    @property
    def release_template(self) -> str:
        return getattr(self, "_release_template", self.name)

    def release_description(self, version: Version) -> Optional[str]:
        descriptions = getattr(self, "_release_descriptions", None)
        if descriptions is None:
            return None
        return descriptions.get(
            str(version),
            descriptions.get(
                version.series(), descriptions.get(str(version.major), None)
            ),
        )

    @staticmethod
    def _is_release_series_valid(series: str) -> bool:
        raise NotImplementedError()

    @staticmethod
    def _branch_name_from_series(series: str) -> str:
        return "stable-" + series

    @staticmethod
    def _version_from_tag(tag_name: str) -> Version:
        exp = re.compile(r"v(\d*)\.(\d*)\.(\d*)$")
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

    @staticmethod
    def _is_build_running(build: jenkinsapi.build) -> bool:
        build_status_update_try_count = 20
        while build_status_update_try_count >= 0:
            try:
                is_running = build.is_running()
                return is_running
            except requests.exceptions.ConnectionError:
                build_status_update_try_count = build_status_update_try_count - 1
                if build_status_update_try_count == 0:
                    raise

    def _ci_release_job_name(self, version):
        series = "{}.{}".format(version.major, version.minor)
        return "{}_v{}_release".format(self.name.lower(), series)

    def _update_version(self, new_version: Version) -> None:
        raise NotImplementedError()

    def _get_tag_str(self, version: Version) -> str:
        raise NotImplementedError()

    def _commit_and_tag(self, new_version: Version, no_sign: bool) -> None:
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

    def _new_changelog_section(self, new_version: Version, tagline: str):
        today = date.today()

        title = "{}-{:02d}-{:02d} {} {}".format(
            today.year,
            today.month,
            today.day,
            self.changelog_project_name,
            str(new_version),
        )
        if tagline:
            title = title + " ({})".format(tagline)
        title = title + "\n"

        latest_tag_name = self._latest_tag_name()
        for ref in self._repo.refs:
            if ref.name == latest_tag_name:
                latest_tag_sha = ref.commit.hexsha
                break

        changelog_new_section = [title]
        for commit in self._repo.iter_commits():
            if commit.hexsha == latest_tag_sha:
                break
            entry = "\t* {}\n".format(commit.summary)
            changelog_new_section.append(entry)

        return changelog_new_section

    def _update_changelog(self, new_version: Version, tagline: str):
        echo("Updating ChangeLog... ".format(self.name), nl=False)
        changelog_new_section = self._new_changelog_section(new_version, tagline)
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

    def _get_release_body(
        self,
        repo: github3.repos.repo.Repository,
        tagline: str,
        version: Version,
        tag: str,
        previous_version: Version,
        previous_tag: str,
    ):
        new_changelog_section = self._new_changelog_section(version, tagline)
        body = self.release_template.format(
            name=self.name,
            changelog_project_name=self.changelog_project_name,
            tagline=tagline,
            tag=tag,
            version=str(version),
            series=version.series(),
            previous_tag=previous_tag,
            previous_version=previous_version,
            repo_url=repo.html_url,
            changelog="\n".join(new_changelog_section),
            release_description=self.release_description(version),
        )

        print("Release notes\n\n{}\n\n".format(body))
        if confirm(
            "Would you like to edit the release notes printed above? (Opens in an external editor)?"
        ):
            with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as f:
                f.write(body)
                f.flush()
                if os.system("editor {}".format(f.name)) == 0:
                    f.seek(0)
                    body = f.read()
        return body

    def _create_github_release(
        self,
        repo: github3.repos.repo.Repository,
        tag: str,
        body: list[str],
        prerelease: bool = False,
    ) -> None:
        echo(
            "Creating new GitHub release at {repo_url}... ".format(
                self.name, repo_url=repo.html_url
            ),
            nl=False,
        )
        repo.create_release(tag, name=tag, body=body, prerelease=prerelease)
        echo(style("✓", fg="green", bold=True))

    def _generate_artifact(
        self, version: Version, no_sign: bool, reuse_last_build_artifacts: bool
    ) -> str:
        job_name = self._ci_release_job_name(version)
        server = jenkinsapi.jenkins.Jenkins(self._ci_url, self._ci_user, self._ci_token)
        if reuse_last_build_artifacts:
            echo(
                style("Getting last build job ")
                + style(job_name, fg="white", bold=True)
                + style("... "),
                nl=False,
            )
            job = server[job_name]
            build = job.get_last_good_build()
            echo(style("✓", fg="green", bold=True))
        else:
            echo(
                style("Launching build job ")
                + style(job_name, fg="white", bold=True)
                + style("... "),
                nl=False,
            )

            # jenkinsapi 0.3.11 does not handle timeouts nor does it allow
            # retries. This may be changed in 0.3.12.
            # See: https://github.com/pycontribs/jenkinsapi/issues/767
            #
            # Meanwhile, simply retry and hope for the best.
            create_job_try_count = 20
            while create_job_try_count >= 0:
                try:
                    job = server.create_job(job_name, None)
                    break
                except requests.exceptions.ConnectionError:
                    create_job_try_count = create_job_try_count - 1
                    if create_job_try_count == 0:
                        raise

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

            delay_secs = 1
            with progressbar(
                length=estimated_duration_secs,
                show_eta=True,
                label="Building on " + build.get_slave(),
            ) as progress:
                last_update_time = time.monotonic()
                while self._is_build_running(build):
                    time.sleep(delay_secs)
                    now = time.monotonic()
                    progress.update(now - last_update_time)
                    last_update_time = now

        build_status = build.poll()
        # Allow release builds with warnings
        if build_status["result"] not in ["SUCCESS", "UNSTABLE"]:
            echo(
                style(
                    'Build failed with status "{status}" 🤯'.format(
                        status=build_status["result"]
                    ),
                    fg="red",
                    bold=True,
                )
            )
            raise AbortedRelease()

        release_tarball_artifact = None
        # Look for an artifact that looks like a release tarball
        for artifact in build.get_artifacts():
            if str(version) in artifact.filename and ".tar" in artifact.filename:
                release_tarball_artifact = artifact
                break

        if release_tarball_artifact is None:
            echo(
                style(
                    "Unexpected artifacts generated by the release job 🤯",
                    fg="red",
                    bold=True,
                )
            )
            echo("Build artifact files:")
            for artifact in build.get_artifacts():
                echo("  {filename}".format(filename=artifact.filename))

            raise AbortedRelease()

        return ReleaseArtifact(release_tarball_artifact, no_sign)

    def release(
        self,
        series: str,
        tagline: str,
        dry: bool,
        rebuild: bool,
        release_type: ReleaseType,
        no_sign: bool,
        reuse_last_build_artifacts: bool,
    ) -> str:
        if not self._is_release_series_valid(series):
            raise InvalidReleaseSeriesError()

        self._clone_repo()

        branch_name = self._branch_name_from_series(series)
        branch_exists = self._branch_exists(branch_name)

        if rebuild:
            if not branch_exists:
                raise InvalidReleaseRebuildOptionError()

            self._set_current_branch(branch_name, False)
            latest_tag_name = self._latest_tag_name()
            release_version = self._version_from_tag(latest_tag_name)
            echo(
                style("Rebuilding artifact of version ")
                + style(str(release_version), fg="white", bold=True)
            )
        elif not branch_exists:
            echo(
                "Branch "
                + style(branch_name, fg="white", bold=True)
                + " does not exist"
            )
            if release_type != ReleaseType.RELEASE_CANDIDATE:
                raise InvalidReleaseTypeError()

            release_version = self._version_from_series(series)
            release_version = Version(
                release_version.major, release_version.minor, 0, 1
            )
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
                if latest_version.rc is not None:
                    patch = 0
                else:
                    patch = latest_version.patch + 1
                minor = latest_version.minor
                rc = None

            release_version = Version(major, minor, patch, rc)
            echo(
                style("Updating version from ")
                + style(str(latest_version), fg="white", bold=True)
                + style(" to ")
                + style(str(release_version), fg="white", bold=True)
            )

        gh = github3.login(self._github_user, token=self._github_token)
        github_urls = [x for x in self._git_urls if x.find("github.com") != -1]
        if not rebuild:
            self._update_changelog(release_version, tagline)
            self._commit_and_tag(release_version, no_sign)

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

        if len(github_urls) > 0:
            repos = []
            for github_url in github_urls:
                owner, repo_name = github_url.split(":")[1].split("/")
                repo = gh.repository(owner, repo_name.rstrip(".git"))
                has_release = False
                for release in repo.releases():
                    if release.tag_name == self._get_tag_str(release_version):
                        has_release = True
                        break
                if not has_release:
                    repos.append(repo)

            if (
                len(repos) > 0
                and not dry
                and confirm(
                    style("Create GitHub releases at ")
                    + style(
                        ", ".join([repo.html_url for repo in repos]),
                        fg="white",
                        bold=True,
                    )
                    + style("?")
                )
            ):
                body = self._get_release_body(
                    repos[0],
                    tagline,
                    release_version,
                    self._get_tag_str(release_version),
                    latest_version,
                    self._get_tag_str(latest_version),
                )
                for repo in repos:
                    self._create_github_release(
                        repo,
                        self._get_tag_str(release_version),
                        body,
                        release_type != ReleaseType.STABLE,
                    )
            else:
                pass

        artifact = self._generate_artifact(
            release_version, no_sign, reuse_last_build_artifacts
        )
        artifact.upload(self._upload_location)
        artifact.upload_to_github(gh, github_urls, self._get_tag_str(release_version))

        return ReleaseDescriptor(self.name, release_version, self._repo_base_path)
