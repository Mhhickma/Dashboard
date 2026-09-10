"""Server-only GitHub dispatch/artifact transport. No credentials enter the UI."""
import io
import json
import os
import subprocess
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

REPO='Mhhickma/Dashboard'
WORKFLOW='scan-film-research.yml'

def token():
    value=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if value:return value
    process=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,timeout=20,cwd=Path(__file__).resolve().parent,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never'})
    fields=dict(line.split('=',1) for line in process.stdout.splitlines() if '=' in line)
    if process.returncode or not fields.get('password'):raise ValueError('GitHub sign-in is needed on this PC to start scans')
    return fields['password']

def api(path,data=None):
    req=urllib.request.Request('https://api.github.com/repos/'+REPO+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'FilmResearch'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            content=response.read();return json.loads(content) if content else {}
    except urllib.error.HTTPError as error:raise ValueError(f'GitHub returned {error.code}. Check repository Actions permission and workflow deployment.') from None
    except (urllib.error.URLError,TimeoutError):raise ValueError('GitHub did not respond. Check the scan status before trying another dispatch.') from None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def artifact(artifact_id):
    # Explicitly strip the credential before following GitHub's signed artifact redirect.
    req=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/artifacts/{int(artifact_id)}/zip',headers={'Authorization':'Bearer '+token(),'User-Agent':'FilmResearch'})
    try:
        urllib.request.build_opener(NoRedirect).open(req,timeout=30)
    except urllib.error.HTTPError as error:
        if error.code!=302:raise ValueError('Artifact download unavailable') from None
        url=error.headers.get('Location','')
        if not url.startswith('https://'):raise ValueError('Invalid artifact redirect')
    else:raise ValueError('Missing artifact redirect')
    import tempfile
    result=tempfile.TemporaryFile()
    try:
        with urllib.request.urlopen(url,timeout=120) as response:
            while chunk:=response.read(1024*1024):result.write(chunk)
        result.seek(0);return result
    except Exception:result.close();raise ValueError('Artifact download interrupted') from None

def restore():
    # Persisted artifacts are serialized by the workflow concurrency group.
    artifacts=api('/actions/artifacts?name=film-research-checkpoint&per_page=100')['artifacts']
    artifacts=[a for a in artifacts if a.get('workflow_run',{}).get('head_branch')=='main']
    if not artifacts:
        previous=api('/actions/workflows/'+WORKFLOW+'/runs?status=success&per_page=1')['workflow_runs']
        if previous:raise ValueError('Research checkpoint missing; refusing to fall back to an older scanner cache')
        # Seed the cache from the retired scanner if its checkpoint is still available.
        artifacts=api('/actions/artifacts?name=influencer-checkpoint&per_page=100')['artifacts']
        artifacts=[a for a in artifacts if a.get('workflow_run',{}).get('head_branch')=='main']
    if not artifacts:raise ValueError('No checkpoint available; refusing to silently repeat paid scans')
    item=artifacts[0]
    if item.get('expired'):raise ValueError('Checkpoint expired; restore a saved checkpoint before scanning')
    with artifact(item['id']) as stream,zipfile.ZipFile(stream) as archive:
        target=Path('.research-scan/checkpoint.sqlite');target.parent.mkdir(exist_ok=True)
        with archive.open('checkpoint.sqlite') as source,target.open('wb') as out:
            while chunk:=source.read(1024*1024):out.write(chunk)

if __name__=='__main__':
    try:restore()
    except Exception:
        print('Checkpoint restore failed. No Keepa requests were made.');raise SystemExit(1)
