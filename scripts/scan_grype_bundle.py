"""Supplemental native CPE/PURL analysis of the exact verified distribution.

No application files are uploaded. Only the public vulnerability DB is fetched.
Tool matches are candidates for applicability review, never publication approval.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from release_bundle import verify_bundle,write_json

VERSION='0.122.0'
EXE_SHA='d4c07a34bfd9aea9846d00f94093e909420bb1e59958a5907708f6b9f28209c3'
ARCHIVE_SHA='617017fbf9078bb9dff57c04c9e59e4dd7b9c93f861640e136fdd5af20263891'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def assess(data,returncode,positive):
    if returncode!=0 or not isinstance(data,dict) or not isinstance(data.get('matches'),list):
        return {'status':'error','findings':None}
    if data.get('descriptor',{}).get('version')!=VERSION or not data.get('descriptor',{}).get('db',{}).get('status',{}).get('valid'):
        return {'status':'incomplete','findings':None}
    if not isinstance(positive,dict) or not any(m.get('vulnerability',{}).get('id')=='CVE-2014-0160' for m in positive.get('matches',[])):
        return {'status':'incomplete','reason':'Native CPE positive control not detected','findings':None}
    return {'status':'findings_require_review' if data['matches'] else 'completed_no_reported_findings',
            'findings':len(data['matches'])}


def run(args):
    facts=verify_bundle(args.assets,args.commit,args.run_id)
    if sha(args.grype)!=EXE_SHA:raise ValueError('Pinned official Windows Grype executable required')
    args.out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env['GRYPE_CHECK_FOR_APP_UPDATE']='false'
    env['GRYPE_DB_CACHE_DIR']=str(args.database_dir.resolve() if args.database_dir else args.out.resolve()/'db')
    if args.database_dir:env['GRYPE_DB_AUTO_UPDATE']='false'
    report=dict(source_commit=args.commit,build_run_id=str(args.run_id),archive_sha256=facts['archive_sha256'],
                release_approved=False,tool='grype',version=VERSION,executable_sha256=EXE_SHA,
                tool_archive_sha256=ARCHIVE_SHA,started_utc=datetime.now(timezone.utc).isoformat())
    report['status']='running'
    write_json(args.out/'grype-scan-report.json',report)
    positive_bom=dict(bomFormat='CycloneDX',specVersion='1.6',version=1,components=[dict(type='library',name='OpenSSL',version='1.0.1f',cpe='cpe:2.3:a:openssl:openssl:1.0.1f:*:*:*:*:*:*:*')])
    write_json(args.out/'positive-control.bom.json',positive_bom)
    def execute(name,bom):
        output=args.out/(name+'.json')
        with (args.out/(name+'.stderr.txt')).open('wb') as stderr:
            try:
                result=subprocess.run([str(args.grype),'sbom:'+str(bom.resolve()),'-o','json','--file',str(output.resolve())],
                                      env=env,stdin=subprocess.DEVNULL,stdout=stderr,stderr=stderr,timeout=args.timeout,check=False)
                code=result.returncode
            except (OSError,subprocess.TimeoutExpired) as error:
                return None,None,type(error).__name__
        try:return json.loads(output.read_text(encoding='utf8')),code,None
        except (OSError,ValueError):return None,code,'InvalidOrMissingJson'
    actual,code,error=execute('grype',args.assets/'bom.cdx.json')
    report['action']='positive_control';report['candidate_scan_returncode']=code
    write_json(args.out/'grype-scan-report.json',report)
    # Reuse precisely the DB that scanned the candidate for the positive control.
    env['GRYPE_DB_AUTO_UPDATE']='false'
    positive,positive_code,positive_error=execute('positive-control',args.out/'positive-control.bom.json')
    result=assess(actual,code,positive if positive_code==0 else None)
    report.update(result,error_type=error,positive_control_error=positive_error)
    report['positive_control_verified']=bool(positive_code==0 and positive and any(m.get('vulnerability',{}).get('id')=='CVE-2014-0160' for m in positive.get('matches',[])))
    inventory=json.loads((args.assets/'sbom.json').read_text(encoding='utf8'))
    report['coverage']={'unmapped_native':inventory['unresolved_native'],
                        'native_without_cpe_or_purl':[c['name'] for c in inventory['native_components'] if not c.get('cpe') and not c.get('purl')],
                        'native_license_issues':inventory['native_license_issues'],
                        'upstream_fork_review_required':[c['name'] for c in inventory['native_components'] if c.get('provenance',{}).get('upstream_libffi_version')=='NOASSERTION']}
    report['limitations']=['CPE/PURL matching evaluates declared identities, not exploitability or all embedded code.',
                          'File hashes establish inventory identity, not complete vulnerability coverage.',
                          'Every match and uncovered fork requires applicability review; no automatic suppression or publication approval.']
    if actual:
        report['database']=actual['descriptor']['db']
        report['matches']=[{'component':m['artifact']['name'],'version':m['artifact']['version'],
                            'id':m['vulnerability']['id'],'severity':m['vulnerability']['severity']} for m in actual['matches']]
    database=Path(env['GRYPE_DB_CACHE_DIR'])/'6'/'vulnerability.db'
    if database.is_file():report['database_file_sha256']=sha(database)
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    write_json(args.out/'grype-scan-report.json',report)
    return 0 if result['status']=='completed_no_reported_findings' and not any(report['coverage'].values()) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('assets','out','grype'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--commit',required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--database-dir',type=Path);p.add_argument('--timeout',type=int,default=900)
    a=p.parse_args();raise SystemExit(run(a))
