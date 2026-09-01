"""GitHub release upgrader: list last 3 releases and switch the installed tag."""

import json
import os
import re
import shutil
import tarfile
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import request, send_from_directory
from flask_cors import cross_origin

GITHUB_REPO = os.environ.get('PIAUTO_GITHUB_REPO', 'karpus2807/piauto').strip()
RELEASE_LIMIT = 3
CACHE_SECONDS = 120
STATUS_PATH = os.environ.get('PIAUTO_UPGRADE_STATUS', '/opt/pironman5/upgrade-status.json')
INSTALLED_PATH = os.environ.get('PIAUTO_INSTALLED_RELEASE', '/opt/pironman5/installed-release.json')
LOG_PATH = os.environ.get('PIAUTO_UPGRADE_LOG', '/var/log/pironman5/upgrade.log')
VENV_PYTHON = os.environ.get('PIAUTO_VENV_PYTHON', '/opt/pironman5/venv/bin/python3')
SERVICE_NAME = os.environ.get('PIRONMAN5_SERVICE', 'pironman5')
USER_AGENT = 'piauto-upgrader'

_TAG_RE = re.compile(r'^v?\d[\w.\-+]*$')
_cache = {'at': 0, 'payload': None}
_lock = threading.Lock()
_apply_thread = None


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def _append_log(line):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"{_now_iso()} {line}\n")
    except Exception:
        pass


def _http_json(url):
    req = Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': USER_AGENT,
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urlopen(req, timeout=20) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw)


def _norm_tag(tag):
    return (tag or '').strip().lstrip('v')


def _current_versions():
    versions = {}
    try:
        import pm_auto
        versions['pm_auto'] = getattr(pm_auto, '__version__', 'unknown')
    except Exception:
        versions['pm_auto'] = 'unknown'
    try:
        import pm_dashboard
        versions['pm_dashboard'] = getattr(pm_dashboard, '__version__', 'unknown')
    except Exception:
        versions['pm_dashboard'] = 'unknown'
    installed = _read_json(INSTALLED_PATH, {}) or {}
    versions['release_tag'] = installed.get('tag') or ''
    return versions


def _is_current_release(tag, versions):
    if not tag:
        return False
    installed_tag = versions.get('release_tag') or ''
    if installed_tag and _norm_tag(installed_tag) == _norm_tag(tag):
        return True
    auto = _norm_tag(versions.get('pm_auto') or '')
    dash = _norm_tag(versions.get('pm_dashboard') or '')
    t = _norm_tag(tag)
    return bool(t) and t in (auto, dash)


def _ver_tuple(value):
    nums = []
    for part in re.split(r'[.\-+_]', _norm_tag(value)):
        if part.isdigit():
            nums.append(int(part))
        elif nums:
            break
    return tuple(nums) if nums else (0,)


def _ver_cmp(left, right):
    a, b = _ver_tuple(left), _ver_tuple(right)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def _direction(tag, versions):
    if _is_current_release(tag, versions):
        return 'current'
    current = versions.get('release_tag') or versions.get('pm_auto') or ''
    cmp_value = _ver_cmp(tag, current)
    if cmp_value > 0:
        return 'update'
    if cmp_value < 0:
        return 'downgrade'
    return 'switch'


def _fetch_releases():
    repo = GITHUB_REPO
    url = f'https://api.github.com/repos/{repo}/releases?per_page={RELEASE_LIMIT}'
    items = []
    source = 'releases'
    try:
        data = _http_json(url)
        if isinstance(data, list):
            for rel in data[:RELEASE_LIMIT]:
                if not isinstance(rel, dict):
                    continue
                if rel.get('draft'):
                    continue
                items.append({
                    'tag': rel.get('tag_name') or '',
                    'name': rel.get('name') or rel.get('tag_name') or '',
                    'body': (rel.get('body') or '').strip(),
                    'published_at': rel.get('published_at') or '',
                    'html_url': rel.get('html_url') or '',
                    'prerelease': bool(rel.get('prerelease')),
                })
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        _append_log(f'GitHub releases fetch failed: {exc}')

    if not items:
        source = 'tags'
        try:
            tags = _http_json(f'https://api.github.com/repos/{repo}/tags?per_page={RELEASE_LIMIT}')
            if isinstance(tags, list):
                for tag in tags[:RELEASE_LIMIT]:
                    name = (tag or {}).get('name') or ''
                    if not name:
                        continue
                    items.append({
                        'tag': name,
                        'name': name,
                        'body': 'GitHub tag (no Release notes yet).',
                        'published_at': '',
                        'html_url': f'https://github.com/{repo}/releases/tag/{name}',
                        'prerelease': False,
                    })
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            _append_log(f'GitHub tags fetch failed: {exc}')
            raise

    return {
        'repo': repo,
        'source': source,
        'releases': items[:RELEASE_LIMIT],
    }


def _cached_catalog(force=False):
    now = time.time()
    if not force and _cache['payload'] and (now - _cache['at']) < CACHE_SECONDS:
        return _cache['payload']
    payload = _fetch_releases()
    _cache['at'] = now
    _cache['payload'] = payload
    return payload


def _status():
    data = _read_json(STATUS_PATH, {
        'state': 'idle',
        'tag': '',
        'message': '',
        'started_at': '',
        'finished_at': '',
    }) or {}
    return data


def _set_status(**kwargs):
    data = _status()
    data.update(kwargs)
    _write_json(STATUS_PATH, data)
    return data


def _run(cmd, cwd=None):
    import subprocess
    _append_log('$ ' + ' '.join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.stdout:
        for line in proc.stdout.splitlines():
            _append_log(line)
    if proc.returncode != 0:
        raise RuntimeError(f'command failed ({proc.returncode}): {" ".join(cmd)}')
    return proc


def _installed_versions(py):
    import subprocess
    code = (
        'import json,pm_auto,pm_dashboard;'
        'print(json.dumps({"pm_auto": pm_auto.__version__,'
        '"pm_dashboard": pm_dashboard.__version__}))'
    )
    proc = subprocess.run(
        [py, '-c', code],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {}


def _python_bin():
    if os.path.isfile(VENV_PYTHON) and os.access(VENV_PYTHON, os.X_OK):
        return VENV_PYTHON
    import sys
    return sys.executable


def _download_archive(tag, dest_tar):
    url = f'https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz'
    _append_log(f'downloading {url}')
    req = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(req, timeout=120) as resp, open(dest_tar, 'wb') as out:
        shutil.copyfileobj(resp, out)


def _extract_root(tar_path, dest_dir):
    base = os.path.abspath(dest_dir)
    with tarfile.open(tar_path, 'r:gz') as tar:
        for member in tar.getmembers():
            dest = os.path.abspath(os.path.join(dest_dir, member.name))
            if dest != base and not dest.startswith(base + os.sep):
                raise RuntimeError('unsafe archive path')
        tar.extractall(dest_dir)
    for name in os.listdir(dest_dir):
        path = os.path.join(dest_dir, name)
        if os.path.isdir(path) and os.path.isdir(os.path.join(path, 'pm_auto')):
            return path
    raise RuntimeError('archive did not contain pm_auto/')


def _apply_release(tag):
    _set_status(state='running', tag=tag, message=f'Downloading {tag}…', started_at=_now_iso(), finished_at='')
    work = tempfile.mkdtemp(prefix='piauto-upgrade-')
    try:
        tar_path = os.path.join(work, 'src.tar.gz')
        _download_archive(tag, tar_path)
        _set_status(message=f'Extracting {tag}…')
        root = _extract_root(tar_path, work)
        py = _python_bin()
        _set_status(message=f'Installing {tag} into venv…')
        # force-reinstall so older tags can downgrade, not only upgrade
        pip_install = [py, '-m', 'pip', 'install', '--force-reinstall', '--no-cache-dir']
        _run(pip_install + [os.path.join(root, 'pm_dashboard')])
        _run(pip_install + [os.path.join(root, 'pm_auto')])
        versions = _installed_versions(py)
        _write_json(INSTALLED_PATH, {
            'tag': tag,
            'repo': GITHUB_REPO,
            'installed_at': _now_iso(),
            'pm_auto': versions.get('pm_auto'),
            'pm_dashboard': versions.get('pm_dashboard'),
        })
        _set_status(state='success', tag=tag, message=f'Installed {tag}. Restarting service…', finished_at=_now_iso())
        _append_log(f'installed {tag}')
        try:
            _run(['systemctl', 'restart', SERVICE_NAME])
        except Exception as exc:
            _append_log(f'restart warning: {exc}')
            _set_status(message=f'Installed {tag}. Restart pironman5 manually if the dashboard does not come back.')
    except Exception as exc:
        _append_log(traceback.format_exc())
        _set_status(state='error', tag=tag, message=str(exc), finished_at=_now_iso())
    finally:
        shutil.rmtree(work, ignore_errors=True)


def register_upgrade_routes(app, api_prefix, static_folder):
    @app.route('/update')
    @app.route('/update/')
    @app.route('/upgrade')
    @app.route('/upgrade/')
    @cross_origin()
    def upgrade_index():
        return send_from_directory(f'{static_folder}/upgrade', 'index.html')

    @app.route('/update/<path:filename>')
    @app.route('/upgrade/<path:filename>')
    @cross_origin()
    def upgrade_assets(filename):
        return send_from_directory(f'{static_folder}/upgrade', filename)

    @app.route(f'{api_prefix}/get-upgrades')
    @cross_origin()
    def get_upgrades():
        versions = _current_versions()
        error = None
        try:
            catalog = _cached_catalog(force=request.args.get('refresh') == '1')
        except Exception as exc:
            catalog = {'repo': GITHUB_REPO, 'source': 'error', 'releases': []}
            error = str(exc)
        releases = []
        for item in catalog.get('releases') or []:
            row = dict(item)
            row['current'] = _is_current_release(row.get('tag'), versions)
            row['direction'] = _direction(row.get('tag'), versions)
            releases.append(row)
        return {
            'status': error is None,
            'error': error,
            'data': {
                'repo': catalog.get('repo'),
                'source': catalog.get('source'),
                'current': versions,
                'releases': releases,
                'job': _status(),
            },
        }

    @app.route(f'{api_prefix}/upgrade-status')
    @cross_origin()
    def upgrade_status():
        return {'status': True, 'data': _status()}

    @app.route(f'{api_prefix}/apply-upgrade', methods=['POST'])
    @cross_origin()
    def apply_upgrade():
        global _apply_thread
        body = request.get_json(silent=True) or {}
        tag = str(body.get('tag') or '').strip()
        if not tag or not _TAG_RE.match(tag):
            return {'status': False, 'error': 'Invalid release tag'}, 400
        try:
            catalog = _cached_catalog(force=True)
        except Exception as exc:
            return {'status': False, 'error': f'Could not verify GitHub releases: {exc}'}, 502
        allowed = {item.get('tag') for item in (catalog.get('releases') or [])}
        if tag not in allowed:
            return {
                'status': False,
                'error': f'{tag} is not in the last {RELEASE_LIMIT} GitHub releases',
            }, 400
        with _lock:
            job = _status()
            if job.get('state') == 'running' and _apply_thread and _apply_thread.is_alive():
                return {'status': False, 'error': 'An upgrade is already running', 'data': job}, 409
            _set_status(state='running', tag=tag, message=f'Starting {tag}…', started_at=_now_iso(), finished_at='')
            _apply_thread = threading.Thread(target=_apply_release, args=(tag,), daemon=True)
            _apply_thread.start()
        return {'status': True, 'data': _status()}
