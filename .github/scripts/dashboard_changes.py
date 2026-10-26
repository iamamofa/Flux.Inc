"""Limit weekly dashboard proposals before exporting or applying their patches."""
import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


ALLOWED_FILES = {
    'inventory/views.py',
    'inventory/tests.py',
    'control/views.py',
    'control/tests.py',
    'control/templates/control/overview.html',
    'control/static/control/portal_refined.css',
    'static/css/dashboard.css',
    'static/js/dashboard.js',
    'static/js/dashboard_charts.js',
    'docs/dashboard-roadmap.md',
    'docs/dashboard-upgrade-log.md',
}
ALLOWED_PATTERNS = (
    'inventory/templates/inventory/dashboard_*.html',
    'inventory/templates/inventory/partials/dashboard_*.html',
    'inventory/dashboard_*.py',
    'control/dashboard_*.py',
    'static/js/dashboard_*.js',
    'static/css/dashboard_*.css',
    'control/static/control/dashboard_*.js',
    'control/static/control/dashboard_*.css',
)
MAX_FILES = 30
MAX_PATCH_BYTES = 250_000


class ProposalError(ValueError):
    pass


def git(root, *arguments):
    result = subprocess.run(
        ['git', '-C', str(root), *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ProposalError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def validate_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name:
        raise ProposalError(f'Invalid proposal path: {name}')
    matches = any(
        len(path.parts) == len(PurePosixPath(pattern).parts) and path.match(pattern)
        for pattern in ALLOWED_PATTERNS
    )
    if name not in ALLOWED_FILES and not matches:
        raise ProposalError(f'Outside the dashboard upgrade scope: {name}')


def validate_worktree(root, base):
    # Compare with the saved base even if an agent accidentally created a commit.
    entries = git(root, 'diff', '--no-renames', '--name-status', '-z', base).decode('utf-8').split('\0')
    changes = set()
    for index in range(0, len(entries) - 1, 2):
        status, name = entries[index:index + 2]
        validate_path(name)
        if status not in {'A', 'M'}:
            raise ProposalError(f'Deletions and file-type changes are not permitted: {name}')
        changes.add(name)
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z').decode('utf-8')
    changes.update(name for name in untracked.split('\0') if name)
    if len(changes) > MAX_FILES:
        raise ProposalError(f'Keep each dashboard proposal within {MAX_FILES} files.')
    for name in sorted(changes):
        validate_path(name)
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ProposalError(f'Only regular source files are permitted: {name}')
        try:
            path.read_bytes().decode('utf-8')
        except UnicodeDecodeError as error:
            raise ProposalError(f'Binary files are not permitted: {name}') from error
    return sorted(changes)


def validate_patch(root, patch):
    content = patch.read_bytes()
    if not content or len(content) > MAX_PATCH_BYTES:
        raise ProposalError(f'Proposal patches must contain 1–{MAX_PATCH_BYTES} bytes.')
    records = git(root, 'apply', '--numstat', '-z', '--', str(patch)).decode('utf-8')
    paths = set()
    for record in filter(None, records.split('\0')):
        added, removed, name = record.split('\t', 2)
        if not added.isdigit() or not removed.isdigit():
            raise ProposalError('Binary patches are not permitted.')
        validate_path(name)
        paths.add(name)
    if not paths or len(paths) > MAX_FILES:
        raise ProposalError(f'Proposal patches must affect 1–{MAX_FILES} source files.')
    git(root, 'apply', '--check', '--', str(patch))


def export_patch(root, base, patch):
    paths = validate_worktree(root, base)
    if not paths:
        return False
    # Stage the validated working tree, including reversions of accidental staged
    # edits, so the exported index cannot contain hidden changes to protected files.
    git(root, 'add', '--all', '--', '.')
    content = git(root, 'diff', '--cached', '--binary', '--no-ext-diff', '--no-textconv', base)
    if len(content) > MAX_PATCH_BYTES:
        raise ProposalError(f'Keep each dashboard proposal within {MAX_PATCH_BYTES} patch bytes.')
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_bytes(content)
    return True


def apply_patch(root, base, patch):
    if git(root, 'status', '--porcelain').strip():
        raise ProposalError('Apply proposals only to a clean checkout.')
    validate_patch(root, patch)
    git(root, 'apply', '--', str(patch))
    validate_worktree(root, base)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('export', 'apply'))
    parser.add_argument('--base', default='HEAD')
    parser.add_argument('--patch', type=Path, required=True)
    args = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').decode().strip())
        if args.operation == 'export':
            changed = export_patch(root, args.base, args.patch.resolve())
            output = os.environ.get('GITHUB_OUTPUT')
            if output:
                with open(output, 'a') as stream:
                    stream.write(f'has-changes={str(changed).lower()}\n')
            print('Dashboard patch exported.' if changed else 'No dashboard changes proposed.')
        else:
            apply_patch(root, args.base, args.patch.resolve())
            print('Dashboard patch applied within the permitted scope.')
    except (ProposalError, ValueError) as error:
        print(f'::error::{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
