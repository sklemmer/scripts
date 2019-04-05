#!/usr/bin/env python3
from typing import List, Any, Union

import click
import docker as moby
from pathlib import Path
from docker.errors import ContainerError, ImageNotFound
import os

docker_socket = 'var/run/docker.sock'
volume_str = '%s:%s'
container_tmp = '/tmp/'


@click.command()
@click.option('--dir', '-v', multiple=True, type=click.STRING, help='Include additionals directories')
@click.option('--aws', is_flag=True, help='Include AWS Credentials')
@click.option('--pwd', '--cwd', is_flag=True, help='Include current working directory')
@click.option('--docker', is_flag=True, help='Include docker socket')
@click.argument('image', nargs=1)
@click.argument('command', nargs=-1)
def cli(aws, pwd, docker, image, command, dir):
    client = moby.DockerClient(base_url='unix://' + docker_socket)

    repository, tag = pull_if_not_exist(image, client)
    volumes = prepare_volumes(aws, pwd, docker, dir)

    try:
        container_logs = client.containers.run(
            image=image,
            volumes=volumes,
            command=command,
            auto_remove=True,
            detach=False,
            # stream=True
        )
        click.echo(container_logs)
    except ContainerError as e:
        click.echo(e, err=True)
        exit(1)


def pull_if_not_exist(image, client):
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


def prepare_volumes(aws, pwd, docker, dir):
    volumes = []
    home = str(Path.home())
    if aws:
        volumes.append(home + '/.aws:/root/.aws:ro')
    if docker:
        volumes.append('/%s:/%s:ro' % (docker_socket, docker_socket))
    if pwd:
        cwd = os.getcwd()
        volumes.append(volume_str % (cwd, container_tmp + os.path.basename(cwd)))

    if dir:
        for path in dir:
            v = path
            if ':' not in path:
                v = volume_str % (path, container_tmp + os.path.basename(path))
            volumes.append(v)
    return volumes


if __name__ == '__main__':
    cli()
