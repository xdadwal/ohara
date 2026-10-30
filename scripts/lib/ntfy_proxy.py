"""Apply the ntfy HTTPS route after proving native topic authentication."""
import datetime
import os
from pathlib import Path
import re
import socket

import bambuddy_proxy
import ntfy
import runtime

MARKER='# Managed by scripts/ntfy-proxy;'


def render(c,root):
    return (root/'configs/nginx/ntfy.template').read_text().replace('@NTFY_HOST@',ntfy.settings(c)[0]).replace(
        '@PROXY_HEADERS@',(root/'configs/nginx/proxy-headers.conf').read_text())


def apply(c,root):
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/ntfy-proxy --apply')
    if c['DOMAIN']!='xdadwal.in':raise ValueError('Automatic proxy install is specific to this verified wildcard host')
    ntfy.status(c,root)
    name=ntfy.settings(c)[0]
    cert=bambuddy_proxy.CERTIFICATE
    for p in [cert,bambuddy_proxy.KEY,'/etc/nginx/conf.d/ohara.conf']:
        if not Path(p).is_file():raise ValueError('Existing wildcard TLS and Ohara proxy are required')
    runtime.run(['openssl','verify','-CApath','/etc/ssl/certs','-untrusted',cert,'-verify_hostname',name,cert])
    runtime.run(['openssl','x509','-in',cert,'-noout','-checkend','86400'])
    folder=Path('/etc/nginx/conf.d');target=folder/'ohara-ntfy.conf'
    if target.is_symlink() or (target.exists() and not target.read_text().startswith(MARKER)):
        raise ValueError('Unmanaged ntfy Nginx site; preserve and review')
    for p in folder.glob('*.conf'):
        if p==target:continue
        if any(name in names.split() for names in re.findall(r'\bserver_name\s+([^;]+);',p.read_text())):
            raise ValueError('Another Nginx file defines ntfy; preserve and review')
    backup=Path('/var/backups/ohara')/('ntfy-proxy-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    bambuddy_proxy.deploy({target:render(c,root).encode()},backup)
    print('ntfy HTTPS route installed; unrelated routes preserved')
