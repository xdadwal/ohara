"""Scoped Kutt HTTPS deployment with native-account guard and LAN-only onboarding."""
import datetime
import ipaddress
import os
from pathlib import Path
import re
import socket

import adguard
import bambuddy_proxy
import config
import kutt
import runtime

MARKER='# Managed by scripts/kutt-proxy;'


def tls_paths(c):
    if c['DOMAIN']!='xdadwal.in' and not all(c.get(k) for k in ('KUTT_TLS_CERT','KUTT_TLS_KEY')):
        raise ValueError('Supply target KUTT_TLS_CERT/KUTT_TLS_KEY paths; never assume this host certificate')
    cert=c.get('KUTT_TLS_CERT',bambuddy_proxy.CERTIFICATE)
    key=c.get('KUTT_TLS_KEY',bambuddy_proxy.KEY)
    for p in (cert,key):
        if not config.PATH.fullmatch(p) or '..' in Path(p).parts:raise ValueError('Unsafe Kutt TLS path')
    return cert,key


def network(c):
    value=c.get('KUTT_LAN_NETWORK',c.get('ADGUARD_NETWORK'))
    if not value:raise ValueError('Discover target LAN subnet and set KUTT_LAN_NETWORK privately before HTTPS onboarding')
    net=ipaddress.ip_network(value,strict=True)
    if net.version!=4 or not any(net.subnet_of(ipaddress.ip_network(n)) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):raise ValueError('Kutt onboarding requires a bounded private IPv4 LAN subnet')
    return str(net)


def render(c,root,*,public=False):
    cert,key=tls_paths(c)
    text=(root/'configs/nginx/kutt.template').read_text()
    replace={'@MODE@':'public user links/login; LAN-only administration' if public else 'LAN-only owner onboarding',
             '@LAN_NETWORK@':network(c),'@KUTT_HOST@':kutt.settings(c)[0],
             '@ONBOARDING_GUARD@':'' if public else 'if ($ohara_kutt_allowed = 0) { return 403; }',
             '@TLS_CERT@':cert,'@TLS_KEY@':key,
             '@PROXY_HEADERS@':(root/'configs/nginx/proxy-headers.conf').read_text()}
    for old,new in replace.items():text=text.replace(old,new)
    return text


def apply(c,root,*,public=False):
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/kutt-proxy --apply with the chosen access mode')
    network(c);kutt.status(c,root)
    if public:kutt.require_accounts(c,root)
    # Prove the configured subnet belongs to the target's actual interface.
    import json
    rows=json.loads(runtime.run(['ip','-j','-4','address','show'],capture=True))
    net=ipaddress.ip_network(network(c))
    if not any(ipaddress.ip_address(a['local']) in net for row in rows for a in row.get('addr_info',[]) if a.get('scope')=='global'):
        raise ValueError('Kutt LAN subnet does not contain a verified host interface')
    name=kutt.settings(c)[0];cert,key=tls_paths(c)
    if not Path(cert).is_file() or not Path(key).is_file():raise ValueError('Provision trusted target DNS/TLS before Kutt proxy activation')
    runtime.run(['openssl','verify','-CApath','/etc/ssl/certs','-untrusted',cert,'-verify_hostname',name,cert])
    runtime.run(['openssl','x509','-in',cert,'-noout','-checkend','86400'])
    directory=Path('/etc/nginx/conf.d');target=directory/'ohara-kutt.conf'
    if target.is_symlink() or target.exists() and not target.read_text().startswith(MARKER):raise ValueError('Unmanaged Kutt route; preserve and review')
    for p in directory.glob('*.conf'):
        if p!=target and any(name in words.split() for words in re.findall(r'\bserver_name\s+([^;]+);',p.read_text())):
            raise ValueError('Another Nginx site defines Kutt; preserve and review')
    backup=Path('/var/backups/ohara')/('kutt-proxy-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    bambuddy_proxy.deploy({target:render(c,root,public=public).encode()},backup)
    print('Kutt '+('public user links with LAN-only administration' if public else 'LAN-only owner onboarding')+' HTTPS enabled; other routes preserved')
