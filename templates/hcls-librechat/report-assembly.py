"""Assemble existing research Markdown/CSV sections without changing calculations.

This checks document construction, not scientific truth or narrative accuracy.
No inference occurs. Original sources remain unchanged and are hash-linked.
"""
import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def cell(value):
    return html.escape(value, quote=False).replace('\\', '\\\\').replace('|', '\\|').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')


def assemble(title, sections):
    if not isinstance(title, str) or not title.strip() or len(title) > 160 or '\n' in title:
        raise ValueError('Use a nonempty one-line document title of at most160 characters.')
    if not isinstance(sections, list) or not 1 <= len(sections) <= 16:
        raise ValueError('Provide one to sixteen existing Markdown or CSV sections.')
    parts = [f'# {title}\n\n']
    provenance = []
    for section in sections:
        label = section.get('title')
        if not isinstance(label, str) or not label.strip() or len(label) > 160 or '\n' in label:
            raise ValueError('Every section needs a nonempty one-line title.')
        source = Path(section['file'])
        data = source.read_bytes()
        text = data.decode('utf-8')
        record = {'title': label, 'format': section['format'], 'source_file': str(source),
                  'source_size_bytes': len(data), 'source_sha256': digest(data)}
        parts.append(f'## {label}\n\n')
        if section['format'] == 'markdown':
            parts.append(text)  # Verbatim original UTF-8 text, including line endings.
            record['rendering'] = 'verbatim UTF-8 Markdown; scientific assertions not re-evaluated'
        elif section['format'] == 'csv':
            rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
            if not rows or not rows[0] or any(not column.strip() for column in rows[0]) or len(set(rows[0])) != len(rows[0]):
                raise ValueError(f'{label}: CSV needs distinct nonempty column headers.')
            if any(len(row) != len(rows[0]) for row in rows[1:]):
                raise ValueError(f'{label}: CSV row width differs from its header; no shifted columns accepted.')
            render = lambda row: '| ' + ' | '.join(cell(value) for value in row) + ' |\n'
            parts += [render(rows[0]), render(['---'] * len(rows[0])), *(render(row) for row in rows[1:])]
            record.update(row_count=len(rows) - 1, column_count=len(rows[0]),
                          rendering='CSV values in original order, Markdown-escaped; no numeric recomputation or rounding')
        else:
            raise ValueError('Supported section formats are markdown and csv.')
        parts.append('\n\n')
        provenance.append(record)
    parts += ['## Document provenance\n\n',
              'Sections were assembled from retained files. This validates file lineage and table construction, not scientific truth, clinical validity or the accuracy of an optional narrative. No new model work was submitted.\n\n']
    for source in provenance:
        parts.append(f"- {source['title']}: {source['source_size_bytes']} bytes; SHA-256 `{source['source_sha256']}`.\n")
    output = ''.join(parts).encode('utf-8')
    return output, {'schema': 'scientific-ai/report-assembly/v1', 'sections': provenance,
        'report_size_bytes': len(output), 'report_sha256': digest(output),
        'scientific_claims_validated': False, 'inference_submitted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    report, provenance = assemble(manifest['title'], manifest['sections'])
    (args.output_dir / 'report.md').write_bytes(report)
    (args.output_dir / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'report_size_bytes': len(report), 'report_sha256': digest(report),
                      'section_count': len(provenance['sections']), 'inference_submitted': False}))


if __name__ == '__main__':
    main()
