import json
from pathlib import Path

import requests

base = Path('c:/Users/Deekshith/Downloads/pytest_cache/NEURONEXUS_TEST_DATASET_90/NEURONEXUS_TEST_DATASET_90')
api = 'http://127.0.0.1:8001'
categories = [
    '01_valid_complete',
    '02_citation_issues',
    '03_structure_issues',
    '04_methodology_quality',
    '05_journal_scope',
    '06_writing_quality',
    '07_formatting',
    '08_tables_figures_equations',
    '09_edge_cases',
]
summary = {cat: {'ok': 0, 'fail': 0, 'files': []} for cat in categories}

for cat in sorted(base.iterdir()):
    if not cat.is_dir():
        continue
    for f in sorted(cat.glob('*.docx')):
        try:
            with open(f, 'rb') as fh:
                up = requests.post(
                    f'{api}/api/documents/upload',
                    files={'file': (f.name, fh, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')},
                    timeout=60,
                )
            if up.status_code != 200:
                summary[cat.name]['fail'] += 1
                summary[cat.name]['files'].append({'file': f.name, 'upload_status': up.status_code, 'upload_text': up.text[:200]})
                continue

            doc_id = up.json()['document_id']
            analyze = requests.post(f'{api}/api/documents/{doc_id}/analyze', json={'journal_id': 'nature'}, timeout=60)
            if analyze.status_code != 200:
                summary[cat.name]['fail'] += 1
                summary[cat.name]['files'].append({'file': f.name, 'analyze_status': analyze.status_code, 'analyze_text': analyze.text[:200]})
                continue

            data = analyze.json()
            quality = requests.post(f'{api}/api/quality/analyze', json={'document_id': doc_id, 'analysis': data}, timeout=60)
            match = requests.post(f'{api}/api/journal/match', json={'document_id': doc_id, 'analysis': data, 'journal_id': 'nature'}, timeout=60)
            report = requests.post(
                f'{api}/api/report/generate',
                json={'document_id': doc_id, 'analysis': data, 'quality_analysis': quality.json() if quality.status_code == 200 else {}, 'selected_journal': 'nature'},
                timeout=60,
            )
            ok = up.status_code == 200 and analyze.status_code == 200 and quality.status_code == 200 and match.status_code == 200 and report.status_code == 200
            if ok:
                summary[cat.name]['ok'] += 1
            else:
                summary[cat.name]['fail'] += 1
                summary[cat.name]['files'].append({
                    'file': f.name,
                    'quality_status': quality.status_code,
                    'match_status': match.status_code,
                    'report_status': report.status_code,
                })
        except Exception as exc:
            summary[cat.name]['fail'] += 1
            summary[cat.name]['files'].append({'file': f.name, 'error': str(exc)[:200]})

print(json.dumps({'by_category': {k: {'ok': v['ok'], 'fail': v['fail']} for k, v in summary.items()}}, indent=2))
for cat, vals in summary.items():
    if vals['fail']:
        print(f'FAIL_CATEGORY {cat} fails={vals["fail"]}')
        for entry in vals['files'][:3]:
            print(' ', entry)
