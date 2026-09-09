#!/usr/bin/env python3
"""Self-contained MCP UI resource for inspecting PDB and mmCIF structures."""

import html
import json
import os
import pathlib
import shlex
import sys
import uuid


ASSET_ROOT = pathlib.Path(os.environ.get('BIONEMO_ASSET_ROOT', '/opt/bionemo')).resolve()
ARTIFACT_ROOT = pathlib.Path(os.environ.get('BIONEMO_ARTIFACT_ROOT', '/workspace/shared/bionemo-artifacts')).resolve()
THREEDMOL = (ASSET_ROOT / '3dmol.js').read_text()


def send(payload):
    print(json.dumps(payload), flush=True)


def javascript_string(value):
    """Encode user-provided structure data safely for an inline script."""
    return json.dumps(value).replace('</', '<\\/')


def _cif_value(row, columns, *names):
    """Return the first non-empty value from a mmCIF atom-site row."""
    for name in names:
        index = columns.get(name)
        if index is not None and index < len(row):
            value = row[index]
            if value not in {'', '.', '?'}:
                return value
    return ''


def normalise_mmcif_for_viewer(structure_text):
    """Convert a coordinate-only mmCIF into conservative PDB records.

    Model outputs commonly contain a minimal ``_atom_site`` loop without the
    entity/secondary-structure categories that browser viewers use to decide
    whether atoms belong to a polymer.  In that case 3Dmol can display a
    protein as isolated sticks.  PDB ``ATOM`` records make the polymer
    designation explicit and let 3Dmol build the cartoon consistently.

    This deliberately handles only the coordinate loop; on an unsupported
    mmCIF the original data is kept and 3Dmol's native parser is used.
    """
    lines = structure_text.splitlines()
    atom_columns = None
    atom_rows = []
    index = 0

    while index < len(lines):
        if lines[index].strip().lower() != 'loop_':
            index += 1
            continue

        index += 1
        headers = []
        while index < len(lines) and lines[index].lstrip().startswith('_'):
            headers.append(lines[index].strip().split()[0].lower())
            index += 1

        if not any(header.startswith('_atom_site.') for header in headers):
            continue

        atom_columns = {header: position for position, header in enumerate(headers)}
        fields = []
        while index < len(lines):
            raw_line = lines[index]
            stripped = raw_line.strip()
            if not stripped or stripped.startswith('#'):
                index += 1
                if fields:
                    return structure_text
                break
            if stripped == 'loop_' or stripped.startswith('_'):
                break
            try:
                fields.extend(shlex.split(raw_line, posix=True))
            except ValueError:
                return structure_text
            while len(fields) >= len(headers):
                atom_rows.append(fields[:len(headers)])
                fields = fields[len(headers):]
            index += 1
        break

    if not atom_columns or not atom_rows:
        return structure_text

    pdb_records = []
    serial = 1
    first_model = None
    for row in atom_rows:
        group = _cif_value(row, atom_columns, '_atom_site.group_pdb').upper()
        if group not in {'ATOM', 'HETATM'}:
            continue
        model = _cif_value(row, atom_columns, '_atom_site.pdbx_pdb_model_num')
        if model:
            if first_model is None:
                first_model = model
            if model != first_model:
                continue
        atom_name = _cif_value(row, atom_columns, '_atom_site.auth_atom_id', '_atom_site.label_atom_id')
        residue = _cif_value(row, atom_columns, '_atom_site.auth_comp_id', '_atom_site.label_comp_id')
        chain = _cif_value(row, atom_columns, '_atom_site.auth_asym_id', '_atom_site.label_asym_id')
        residue_number = _cif_value(row, atom_columns, '_atom_site.auth_seq_id', '_atom_site.label_seq_id')
        insertion = _cif_value(row, atom_columns, '_atom_site.pdbx_pdb_ins_code')
        element = _cif_value(row, atom_columns, '_atom_site.type_symbol')
        altloc = _cif_value(row, atom_columns, '_atom_site.label_alt_id')
        occupancy = _cif_value(row, atom_columns, '_atom_site.occupancy') or '1.00'
        b_factor = _cif_value(row, atom_columns, '_atom_site.b_iso_or_equiv') or '0.00'
        x = _cif_value(row, atom_columns, '_atom_site.cartn_x')
        y = _cif_value(row, atom_columns, '_atom_site.cartn_y')
        z = _cif_value(row, atom_columns, '_atom_site.cartn_z')
        if not atom_name or not residue or not x or not y or not z:
            continue
        try:
            coordinates = (float(x), float(y), float(z))
            residue_id = int(float(residue_number)) if residue_number else serial
            occupancy_value = float(occupancy)
            b_factor_value = float(b_factor)
        except ValueError:
            continue
        record_type = 'ATOM' if group == 'ATOM' else 'HETATM'
        pdb_records.append(
            f'{record_type:<6}{serial:>5} {atom_name[:4]:<4}{(altloc or " ")[0]}'
            f'{residue[:3]:>3} {(chain or " ")[0]}{residue_id:>4}{(insertion or " ")[0]}   '
            f'{coordinates[0]:>8.3f}{coordinates[1]:>8.3f}{coordinates[2]:>8.3f}'
            f'{occupancy_value:>6.2f}{b_factor_value:>6.2f}          {element[:2].rjust(2)}'
        )
        serial += 1

    if not pdb_records:
        return structure_text
    return '\n'.join(pdb_records + ['END', ''])


def viewer_html(structure_text, structure_format, title, structures=None):
    safe_title = html.escape(title)
    if structure_format == 'cif':
        normalised_structure = normalise_mmcif_for_viewer(structure_text)
        if normalised_structure != structure_text:
            structure_text = normalised_structure
            structure_format = 'pdb'
    structure_data = javascript_string(structure_text)
    format_data = javascript_string(structure_format)
    entries = structures or [{'text': structure_text, 'format': structure_format, 'label': title}]
    entries_data = javascript_string(entries)
    entry_options = ''.join(f'<option value="{index}">{html.escape(entry["label"])}</option>' for index, entry in enumerate(entries))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title><style>
:root {{ color-scheme: light; font-family: Inter,ui-sans-serif,system-ui,sans-serif; }} * {{ box-sizing: border-box; }}
html,body {{ min-height:100%; width:100%; overflow-x:hidden; }} body {{ margin:0; background:#f7f9fc; color:#14213d; }} .panel {{ position:relative; border:1px solid #dce3ef; border-radius:12px; overflow:hidden; background:#fff; box-shadow:0 3px 12px #14213d12; }}
.toolbar {{ position:relative; z-index:2; min-height:52px; display:flex; gap:9px; align-items:center; flex-wrap:wrap; padding:10px 12px; border-bottom:1px solid #e8edf5; }}
.title {{ font-weight:650; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-right:auto; max-width:38ch; }} button,select {{ border:1px solid #cbd5e1; border-radius:7px; background:#fff; color:#14213d; font:inherit; font-size:13px; padding:6px 9px; cursor:pointer; }}
button:hover,select:hover {{ border-color:#2563eb; }} button[aria-pressed="true"] {{ color:#fff; border-color:#2563eb; background:#2563eb; }} label {{ color:#475569; font-size:13px; }}
#viewer {{ position:relative; z-index:1; height:480px; min-height:300px; width:100%; overflow:hidden; isolation:isolate; }} .hint {{ position:relative; z-index:2; color:#64748b; font-size:12px; padding:8px 12px; border-top:1px solid #e8edf5; }}
html:fullscreen,html:fullscreen body {{ width:100%; height:100%; background:#f7f9fc; }} html:fullscreen .panel {{ display:flex; flex-direction:column; width:100%; height:100vh; border:0; border-radius:0; box-shadow:none; }} html:fullscreen #viewer {{ flex:1; height:auto; min-height:0; max-height:none; }}
@media (max-width:560px) {{ .title {{ width:100%; max-width:none; }} #viewer {{ min-height:420px; }} }}</style></head>
<body><section class="panel" aria-label="Molecular structure viewer"><div class="toolbar"><div class="title">{safe_title}</div>
<label>Structure <select id="structure" aria-label="Structure">{entry_options}</select></label>
<button id="reset" type="button">Reset view</button><button id="spin" type="button" aria-pressed="false">Start rotation</button>
<label>Representation <select id="style" aria-label="Molecular representation"><option value="cartoon">Cartoon</option><option value="cartoon-sticks">Cartoon + sticks</option><option value="sticks">Sticks</option><option value="surface">Surface</option></select></label><button id="fullscreen" type="button" aria-pressed="false">Full screen</button></div>
<div id="viewer"></div><div id="viewer-status" role="status" class="hint">Loading structure…</div><div class="hint">Drag to rotate · scroll or pinch to zoom · right-drag to pan · Predictions are not experimental validation</div></section>
<script>{THREEDMOL}</script><script>
let viewer; const entries={entries_data}; let spinning=false;
let model, initialView, alphaCarbons=[], polymerAtoms=[], hasCartoonBackbone=false;
function loadStructure(index) {{
  viewer.removeAllModels(); viewer.removeAllShapes(); viewer.removeAllSurfaces();
  const entry=entries[index]; model=viewer.addModel(entry.text,entry.format);
  const atoms=model.selectedAtoms({{}});
  if(!atoms.length) throw new Error('No readable atoms in this structure.');
  if(atoms.some(a=>![a.x,a.y,a.z].every(Number.isFinite))) throw new Error('Invalid atom coordinates.');
  alphaCarbons=model.selectedAtoms({{atom:'CA'}}); polymerAtoms=model.selectedAtoms({{hetflag:false}});
  hasCartoonBackbone=alphaCarbons.length>=4&&polymerAtoms.length>alphaCarbons.length*2;
  const style=entry.format==='sdf'||entry.format==='mol'?'sticks':'cartoon';
  document.getElementById('style').value=style; setRepresentation(style); initialView=viewer.getView();
  document.getElementById('viewer-status').textContent=atoms.length+' atoms · '+entry.format.toUpperCase()+' · '+entry.label;
  document.querySelector('.panel').dataset.viewerReady='true';
}}
function point(atom) {{ return {{x:atom.x,y:atom.y,z:atom.z}}; }}
function backboneFallback() {{
  if(alphaCarbons.length<4) return false;
  const chains=new Map();
  for(const atom of alphaCarbons) {{ const chain=String(atom.chain||''); if(!chains.has(chain)) chains.set(chain,[]); chains.get(chain).push(atom); }}
  const colors=['#2563eb','#7c3aed','#db2777','#0891b2','#16a34a','#d97706']; let chainIndex=0; let segments=0;
  for(const atoms of chains.values()) {{
    atoms.sort((left,right)=>Number(left.resi)-Number(right.resi)); const color=colors[chainIndex++%colors.length];
    for(let index=1;index<atoms.length;index++) {{ const first=atoms[index-1],second=atoms[index]; const delta=Math.hypot(first.x-second.x,first.y-second.y,first.z-second.z); const residueGap=Math.abs(Number(first.resi)-Number(second.resi)); if(delta<=5.2&&residueGap<=2) {{ viewer.addCylinder({{start:point(first),end:point(second),radius:0.34,color,fromCap:1,toCap:1}}); segments++; }} }}
  }}
  return segments>0;
}}
function setRepresentation(name) {{ viewer.setStyle({{}},{{}}); viewer.removeAllSurfaces(); viewer.removeAllShapes(); if(name==='sticks') {{ viewer.setStyle({{}},{{stick:{{radius:0.18,colorscheme:'Jmol'}}}}); }} else if(name==='surface') {{ if(hasCartoonBackbone) viewer.setStyle({{hetflag:false}},{{cartoon:{{color:'spectrum',opacity:0.25}}}}); else viewer.setStyle({{}},{{stick:{{radius:0.15,colorscheme:'Jmol'}}}}); viewer.addSurface($3Dmol.SurfaceType.VDW,{{opacity:0.78,color:'#6b9ed8'}}); }} else if(hasCartoonBackbone) {{ viewer.setStyle({{hetflag:false}},{{cartoon:{{color:'spectrum'}}}}); if(name==='cartoon-sticks') viewer.addStyle({{}},{{stick:{{radius:0.12,colorscheme:'Jmol'}}}}); else viewer.setStyle({{hetflag:true}},{{stick:{{radius:0.12,colorscheme:'Jmol'}}}}); }} else if(!backboneFallback()) {{ viewer.setStyle({{}},{{stick:{{radius:0.18,colorscheme:'Jmol'}}}}); }} viewer.zoomTo(); viewer.render(); }}
function setSpin(enabled) {{ spinning=enabled; viewer.spin(enabled?'y':false,1); const button=document.getElementById('spin'); button.setAttribute('aria-pressed',String(enabled)); button.textContent=enabled?'Auto-rotate':'Start rotation'; }}
function reportHeight() {{ const panel=document.querySelector('.panel'); window.parent.postMessage({{type:'ui-size-change',payload:{{height:Math.ceil(panel.scrollHeight)}}}},'*'); }}
function resizeViewer() {{ viewer.resize(); viewer.render(); reportHeight(); }}
function syncFullscreen() {{ const active=Boolean(document.fullscreenElement); const button=document.getElementById('fullscreen'); button.setAttribute('aria-pressed',String(active)); button.textContent=active?'Exit full screen':'Full screen'; requestAnimationFrame(resizeViewer); }}
async function toggleFullscreen() {{ try {{ if(document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }} catch(error) {{ document.getElementById('viewer-status').textContent='Fullscreen is unavailable in this browser. Rotation and zoom remain available.'; }} }}
function showError(error) {{ document.querySelector('.panel').dataset.viewerReady='false'; document.getElementById('viewer-status').textContent='Unable to display structure: '+error.message; }}
try {{
  viewer=$3Dmol.createViewer(document.getElementById('viewer'),{{backgroundColor:'#f8fafc'}});
  document.getElementById('reset').addEventListener('click',()=>{{setSpin(false);viewer.setView(initialView);viewer.render();}});
  document.getElementById('spin').addEventListener('click',()=>setSpin(!spinning));
  document.getElementById('style').addEventListener('change',(event)=>setRepresentation(event.target.value));
  document.getElementById('structure').addEventListener('change',(event)=>{{try {{loadStructure(Number(event.target.value));}} catch(error) {{showError(error);}}}});
  document.getElementById('fullscreen').addEventListener('click',toggleFullscreen);
  document.addEventListener('fullscreenchange',syncFullscreen); loadStructure(0); setSpin(false);
  window.addEventListener('resize',resizeViewer);
  new ResizeObserver(()=>{{viewer.resize();viewer.render();}}).observe(document.getElementById('viewer'));
}} catch(error) {{ showError(error); }}
requestAnimationFrame(reportHeight); new ResizeObserver(reportHeight).observe(document.querySelector('.panel'));
</script></body></html>'''


def tool_definition():
    return {
        'name': 'protein_viewer',
        'description': 'Render a PDB or mmCIF structure in an inline BioNeMo viewer with rotation, zoom, reset, and representation controls.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'structure_format': {'type': 'string', 'enum': ['pdb', 'cif']},
                'structure_text': {'type': 'string', 'description': 'PDB or mmCIF file contents. Use only for small inline structures.'},
                'structure_path': {'type': 'string', 'description': 'A PDB or mmCIF file saved by the BioNeMo artifact relay under the configured BioNeMo artifact workspace.'},
                'title': {'type': 'string', 'description': 'Optional label shown above the viewer.'},
            },
            'required': ['structure_format'],
        },
    }


def call_viewer(arguments):
    structure_format = arguments.get('structure_format')
    structure_text = arguments.get('structure_text')
    structure_path = arguments.get('structure_path')
    title = arguments.get('title', 'BioNeMo structure')
    if structure_format not in {'pdb', 'cif'}:
        raise ValueError('structure_format must be pdb or cif')
    if structure_text is not None and structure_path is not None:
        raise ValueError('provide exactly one of structure_text or structure_path')
    if structure_path is not None:
        if not isinstance(structure_path, str):
            raise ValueError('structure_path must be a string')
        candidate = pathlib.Path(structure_path).resolve()
        if ARTIFACT_ROOT not in candidate.parents or not candidate.is_file():
            raise ValueError(f'structure_path must be a saved BioNeMo artifact under {ARTIFACT_ROOT}')
        if candidate.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('structure artifact is too large for the inline viewer')
        structure_text = candidate.read_text(encoding='utf-8')
    if not isinstance(structure_text, str) or not structure_text.strip():
        raise ValueError('structure_text or structure_path must contain PDB or mmCIF data')
    if not isinstance(title, str):
        raise ValueError('title must be a string')
    resource_id = f'proteinviewer{uuid.uuid4().hex}'
    return {
        'content': [
            {'type': 'text', 'text': f'Interactive {structure_format.upper()} structure viewer for "{title}". Place the supplied UI resource marker in the response so the viewer is shown inline.'},
            {'type': 'resource', 'resource': {'uri': f'ui://bionemo/protein-viewer/{resource_id}', 'mimeType': 'text/html', 'text': viewer_html(structure_text, structure_format, title)}},
        ],
    }


for line in sys.stdin if __name__ == '__main__' else ():
    request = None
    try:
        request = json.loads(line)
        request_id = request.get('id')
        method = request.get('method')
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'protein-viewer', 'version': '2.0'}}})
        elif method == 'ping':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {}})
        elif method == 'notifications/initialized':
            continue
        elif method == 'tools/list':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': {'tools': [tool_definition()]}})
        elif method == 'tools/call':
            send({'jsonrpc': '2.0', 'id': request_id, 'result': call_viewer(request.get('params', {}).get('arguments', {}))})
    except Exception as error:
        send({'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None, 'error': {'code': -32000, 'message': str(error)}})
