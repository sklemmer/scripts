#!/usr/bin/env python3

"""This script takes some arguments and
passes them along to docker for running tools inside
a container more easily"""

from typing import List, Any, Union

import os

try:
    from pathlib import Path

    Path().expanduser()
except (ImportError, AttributeError):
    from pathlib2 import Path

import click
import docker as moby

from docker.errors import ContainerError

DOCKER_SOCKET = 'var/run/docker.sock'
VOLUME_STR = '%s:%s'
CONTAINER_TMP = '/tmp/'


@click.command()
@click.option('--volume', '-v', multiple=True,
              type=click.STRING,
              help='Include additional directories')
@click.option('--aws', is_flag=True, help='Include AWS Credentials')
@click.option('--pwd', '--cwd', is_flag=True, help='Include current working directory')
@click.option('--interactive', '-i', is_flag=True, help='Include current working directory')
@click.option('--tty', '-t', is_flag=True, help='Include current working directory')
@click.option('--docker', is_flag=True, help='Include docker socket')
@click.argument('image', nargs=1)
@click.argument('command', nargs=-1)
def cli(aws, pwd, docker, image, command, volume, interactive, tty):
    """
    basic command
    :param aws:
    :param pwd:
    :param docker:
    :param image:
    :param command:
    :param dir:
    :return:
    """
    client = moby.DockerClient(base_url='unix://' + DOCKER_SOCKET)

    repository, tag = pull_if_not_exist(image, client)
    volumes = prepare_volumes(aws, pwd, docker, volume)

    exit_code = 1
    try:
        container = client.containers.create(
            image='%s:%s' % (repository, tag),
            volumes=volumes,
            command=command,
            detach=False,
            stdin_open=interactive,
            tty=tty
        )
        container.start()
        click.echo(container.logs(follow=True), nl=False)
        container.remove()
        exit_code = 0
    except ContainerError as e:
        click.echo(e.container.logs(), err=True, nl=False)
        e.container.remove()
    finally:
        exit(exit_code)


def pull_if_not_exist(image, client):
    """
    Pull image from configured registry if it
    does not exist locally
    :param image:
    :param client:
    :return:
    """
    if ':' in image:
        repository = image.split(':')[0]
        tag = image.split(':')[1]
    else:
        repository = image
        tag = 'latest'

    image_list = client.images.list(repository)
    found = False
    for image in image_list:
        if '%s:%s' % (repository, tag) in image.attrs['RepoTags']:
            found = True
            break

    if not found:
        click.echo('No local image %s:%s, try to pull...' % (repository, tag))
        try:
            client.images.pull(repository, tag)
        except Exception:
            click.echo("Could not find image %s:%s in registry" % (repository, tag))
            exit(1)

    return repository, tag


def prepare_volumes(aws, pwd, docker, volume):
    """
    Prepare specified volumes
    allows defining volumes with hostpath:containerpath representation
    if no containerpath is given the script will
    expand it to hostpath:/tmp/basename(hostpath)
    :param aws:
    :param pwd:
    :param docker:
    :param volume:
    :return:
    """
    volumes = []
    home = str(Path.home())
    if aws:
        volumes.append(home + '/.aws:/root/.aws:ro')
    if docker:
        volumes.append('/%s:/%s:ro' % (DOCKER_SOCKET, DOCKER_SOCKET))
    if pwd:
        cwd = os.getcwd()
        volumes.append(VOLUME_STR % (cwd, CONTAINER_TMP + os.path.basename(cwd)))

    if dir:
        for path in volume:
            vol = path
            if ':' not in path:
                vol = VOLUME_STR % (path, CONTAINER_TMP + os.path.basename(path))
            volumes.append(vol)
    return volumes


if __name__ == '__main__':
    cli()
