# SPDX-License-Identifier: MIT
#
# Copyright (c) 2020 Jérémie Galarneau <jeremie.galarneau@gmail.com>

import sys
import logging
import click

from click import echo, style

from reml.lttngtools import LTTngToolsProject
from reml.babeltrace import BabeltraceProject
from reml.project import (
    InvalidReleaseSeriesError,
    InvalidReleaseTypeError,
    ReleaseType,
    AbortedRelease,
)
from reml.config import MissingConfigurationError, MissingConfigurationAttributeError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.argument(
    "project",
    required=True,
    type=click.Choice(["lttng-tools", "babeltrace"], case_sensitive=False),
)
@click.option(
    "--type",
    required=True,
    type=click.Choice(["stable", "candidate"], case_sensitive=False),
    help="type of release",
)
@click.option(
    "--series",
    default=None,
    required=True,
    help="release series for which a release should be produced",
)
@click.option(
    "--dry",
    default=False,
    required=False,
    is_flag=True,
    help="don't publish the resulting release",
)
@click.option(
    "--tagline", default=None, help="tagline of the release to use in the ChangeLog"
)
def main(
    project: str, series: str, type: str, tagline: str, dry: bool, args=None
) -> None:
    logger.debug("Launching reml")

    project_name = project

    if tagline is None:
        echo(style("Preparing release without a tagline 😞", fg="yellow", bold=True))

    if project_name.lower() == "lttng-tools":
        project_class = LTTngToolsProject
    elif project_name.lower() == "babeltrace":
        project_class = BabeltraceProject
    else:
        echo(
            style("🤦‍ Unsupported project ", fg="red")
            + style(project_name, fg="white", bold=True),
            err=True,
        )
        sys.exit(1)

    try:
        project = project_class()
    except MissingConfigurationError as e:
        echo(
            style("🤬 Configuration file was not found at ", fg="red", bold=True)
            + style(e.expected_path, fg="white", bold=True)
        )
        sys.exit(1)
    except MissingConfigurationAttributeError as e:
        echo(
            style("🤦‍ Missing configuration attribute ", fg="red", bold=True)
            + style(e.attribute, fg="white", bold=True)
            + style(" for project ", fg="red", bold=True)
            + style(e.project_name, fg="white", bold=True)
        )
        sys.exit(1)

    try:
        release = project.release(
            series,
            tagline,
            dry,
            ReleaseType.STABLE if type == "stable" else ReleaseType.RELEASE_CANDIDATE,
        )
    except InvalidReleaseSeriesError as e:
        echo(
            style("😬 Unexpected release series ", fg="red", bold=True)
            + style(series, fg="white", bold=True)
            + style(" for project ", fg="red", bold=True)
            + style(project_name, fg="white", bold=True)
        )
        sys.exit(1)
    except InvalidReleaseTypeError as e:
        echo(
            style("😬 Invalid release type ", fg="red", bold=True)
            + style(type, fg="white", bold=True)
            + style(" for release series ", fg="red", bold=True)
            + style(series, fg="white", bold=True)
        )
        sys.exit(1)
    except AbortedRelease as e:
        echo(style("Release aborted 😟", fg="red", bold=True))
        sys.exit(1)

    echo(
        style("🥳 ")
        + style(release.name, fg="white", bold=True)
        + style(" has been released! 🍾")
    )


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
