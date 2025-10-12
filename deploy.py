#!/usr/bin/env python3
"""
PyInfra deployment script to install and configure Caddy web server on Arch Linux.
"""

from pyinfra import config
from pyinfra.operations import files, pacman, systemd

# Use sudo
config.SUDO = True

pacman.packages(
    name="Install Caddy web server",
    packages=["caddy"],
    update=True,
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
)
