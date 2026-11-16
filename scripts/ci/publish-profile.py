"""Publish only validated SVG outputs; checkout credential stays in Git's helper."""
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FILES=('assets/lex-profile/activity-v4.svg','assets/lex-profile/activity-v4-mobile.svg')
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def main():
    if os.environ.get('CIRCLECI')!='true' or os.environ.get('CIRCLE_BRANCH')!='main':
        raise SystemExit('Publication requires CircleCI on main')
    if git('config','--get','remote.origin.url').removesuffix('.git').rstrip('/') not in (
            'https://github.com/brunoflma/brunoflma','git@github.com:brunoflma/brunoflma'):
        raise SystemExit('Unexpected repository')
    if git('rev-parse','HEAD')!=os.environ['CIRCLE_SHA1']:
        raise SystemExit('Checkout differs from pipeline')
    if git('ls-remote','origin','refs/heads/main').split()[0]!=os.environ['CIRCLE_SHA1']:
        raise SystemExit('Main advanced; preserve newer work')
    incoming=Path(sys.argv[1]).resolve()
    for name in FILES:
        path=incoming/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
            raise SystemExit('Invalid panel output')
        if ET.fromstring(path.read_bytes()).tag!='{http://www.w3.org/2000/svg}svg':
            raise SystemExit('Invalid SVG')
        shutil.copyfile(path,ROOT/name)
    if not git('diff','--name-only','--',*FILES):
        print('Public profile is current; no commit needed')
        return
    subprocess.run(['git','add','--',*FILES],cwd=ROOT,check=True)
    if set(git('diff','--cached','--name-only').splitlines())-set(FILES):
        raise SystemExit('Unexpected staged content')
    subprocess.run(['git','-c','user.name=CircleCI','-c','user.email=ci@users.noreply.github.com',
                    'commit','-m','chore: refresh public profile data'],cwd=ROOT,check=True)
    subprocess.run(['git','push','origin','HEAD:refs/heads/main'],cwd=ROOT,check=True)

if __name__=='__main__':
    main()
