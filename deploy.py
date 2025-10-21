#!/usr/bin/env python3
"""
PyInfra deployment script to install and configure Caddy web server on Arch Linux.
"""

from pyinfra import config
from pyinfra.operations import files, pacman, server, systemd

# Use sudo
config.SUDO = True

pacman.packages(
    name="Install dependencies",
    packages=["caddy", "docker", "zip"],
    update=True,
)

files.put(
    name="Copy Caddyfile to /etc/caddy",
    src="Caddyfile",
    dest="/etc/caddy/Caddyfile",
    user="root",
    group="root",
    mode="644",
)

files.sync(
    name="Copy www folder to /usr/share/caddy",
    src="www",
    dest="/usr/share/caddy",
    user="root",
    group="root",
)

systemd.service(
    name="Enable and start Caddy service",
    service="caddy.service",
    running=True,
    enabled=True,
    restarted=True,
)

server.user(
    name="Add github-actions user to docker group",
    user="github-actions",
    groups=["docker"],
    append=True,
)

systemd.service(
    name="Restart github-actions service",
    service="github-actions.service",
    restarted=True,
)
systemd.service(
    name="Enable and start Docker service",
    service="docker.service",
    running=True,
    enabled=True,
)

files.link(
    name="Create symlink /usr/share/caddy/build -> /var/lib/github-actions/build",
    path="/usr/share/caddy/build",
    target="/var/lib/github-actions/build",
    user="root",
    group="root",
    force=True,
)
