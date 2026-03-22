import os
import subprocess  # noqa: S404
import sys
from pathlib import Path


def test_default_payment_model_has_no_pending_migrations():
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'tests.settings_default_payment'
    env['PYTHONPATH'] = os.pathsep.join([
        str(project_root),
        *filter(None, [env.get('PYTHONPATH')]),
    ])

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            'manage.py',
            'makemigrations',
            '--check',
            '--dry-run',
            'getpaid',
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    output = '\n'.join(
        part for part in (result.stdout, result.stderr) if part.strip()
    )
    assert result.returncode == 0, output
