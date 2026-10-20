"""Local code/config provenance shared by manual and automatic recordings."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def save_provenance(folder, cfg):
    from src.utils.paths import APP_ROOT
    root = Path(APP_ROOT)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': 1, 'git_commit': None,
              'source_snapshot': 'source_snapshot.zip'}
    try:
        run = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                             capture_output=True, text=True, timeout=3,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if run.returncode == 0:
            result['git_commit'] = run.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Include working files, including untracked modules; HEAD alone is insufficient.
    paths = [*root.glob('*.py'), *root.glob('requirements*.txt')]
    paths += list((root/'src').rglob('*.py'))
    digest = hashlib.sha256()
    with zipfile.ZipFile(folder/'source_snapshot.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            name = path.relative_to(root).as_posix()
            data = path.read_bytes()
            digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(data).digest())
            archive.writestr(name, data)
    result['source_sha256'] = digest.hexdigest()
    result['automation_version'] = '{}-{}'.format(
        (result['git_commit'] or 'no-git')[:12], result['source_sha256'][:12])
    config = json.dumps(cfg, ensure_ascii=False, sort_keys=True, indent=2)
    (folder/'config_snapshot.json').write_text(config, encoding='utf-8')
    result['config_sha256'] = hashlib.sha256(config.encode('utf-8')).hexdigest()
    (folder/'provenance.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
