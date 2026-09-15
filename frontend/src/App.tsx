import React, { useEffect, useMemo, useState } from 'react'
import './App.css'
import { apiFetch } from './api'
import { apiUrl } from './config'
const DEFAULT_PARAMS: Record<string, any> = {
  carrier_max_overall_width: 38, carrier_width: 36, carrier_deck_length: 63, deck_height: 17.25,
  track_flat_width: 11.5, track_outer_spacing: 36, track_center_gap: 13, flared_guide_height: 3,
  flare_angle: 45, flare_width: 1, ramp_length: 61, ramp_clearance: 1, hinge_pin_dia: .75,
  hinge_barrel_od: 1.25, hinge_barrel_wall: .1875, hinge_barrel_id: .875, hinge_barrel_length: 4,
  hinge_barrel_count: 7, hinge_barrel_gap: .5, hinge_pin_length: 36, stinger_spacing_model_nominal: 37.5,
  stinger_section: '2x2x1/4 Tube', stinger_sleeve_section: '2.5x2.5x3/16 Tube', stinger_sleeve_length: 40,
  stinger_insertion_length: 18, stinger_overlap_length: 40, mount_beam_section: '2x2x1/4 Tube',
  mount_beam_stations: [4, 17, 37], hitch_pin_hole_setback: 3, hitch_pin_hole_dia: .656,
  truck_suspension_drop: 1.5, machine_width: 36, machine_length_oem: 70.5, machine_length_field: 72,
  machine_height: 48, machine_rear_tire_size: '22x8.5-12', machine_front_tire_size: '15x6-6',
  machine_rear_tire_width: 8.5, machine_rear_tire_diameter: 22, machine_front_tire_width: 6,
  machine_front_tire_diameter: 15, machine_curb_weight: 698, fertilizer_hopper_weight: 150, fertilizer_trays_weight: 100,
  spray_tank_gallons: 24, liquid_density_lb_gal: 8.34, vertical_dynamic_factor: 2, braking_factor: .8,
  lateral_factor: .5, material_yield_strength: 46000, target_safety_factor: 2, machine_cg_from_deck_front: 31.5,
  available_stock_lengths: [240, 288], saw_kerf: .125
}
const DESIGN_KEYS = Object.keys(DEFAULT_PARAMS).filter(k => !['available_stock_lengths', 'saw_kerf'].includes(k))
const SHEETS = ['General arrangement', 'Main carrier weldment — plan', 'Main carrier weldment — elevation',
  'Truck mounting assembly', 'Ramp weldment — plan', 'Ramp and hinge detail', 'Fabricated parts',
  'Fabrication schedule', 'Stock cutting plan']
const PARAMETER_FIELDS = [
  ['carrier_width', 'Carrier frame width', 'in', .25], ['carrier_deck_length', 'Deck length', 'in', .25],
  ['deck_height', 'Deck running height', 'in', .25], ['track_flat_width', 'Flat track width', 'in', .25],
  ['flared_guide_height', 'Guide height', 'in', .25], ['flare_angle', 'Guide flare angle', 'deg', 1],
  ['flare_width', 'Flare projection', 'in', .125], ['ramp_length', 'Ramp length', 'in', .25],
  ['ramp_clearance', 'Rear tire clearance', 'in', .25], ['hinge_pin_dia', 'Hinge pin diameter', 'in', .0625],
  ['stinger_insertion_length', 'Stinger insertion', 'in', .25], ['hitch_pin_hole_setback', 'Pin-hole setback', 'in', .125],
  ['stinger_overlap_length', 'Stinger overlap', 'in', .25], ['machine_curb_weight', 'Machine curb weight', 'lb', 1],
  ['spray_tank_gallons', 'Spray tank capacity', 'gal', 1], ['vertical_dynamic_factor', 'Vertical dynamic factor', 'g', .1]
] as const

function fraction(value: number) {
  if (!Number.isFinite(value)) return '—'
  const sign = value < 0 ? '-' : '', n = Math.round(Math.abs(value) * 16), whole = Math.floor(n / 16), rem = n % 16
  if (!rem) return `${sign}${whole}"`
  const gcd = (a: number, b: number): number => b ? gcd(b, a % b) : a
  const d = gcd(rem, 16)
  return `${sign}${whole ? `${whole} ` : ''}${rem / d}/${16 / d}"`
}
const fieldFit = (x: any) => Boolean(x?.field_fit || /CUT TO FIT|FIELD FIT/i.test(x?.notes || ''))
const prep = (x: any) => {
  const note = String(x?.notes || '').replace(/^SQUARE\s*-\s*/i, '').trim()
  return fieldFit(x) ? `CUT TO FIT — APPROX. ${note.replace(/^CUT TO FIT\s*-\s*APPROX\.\s*/i, '')}` : note
}

function App() {
  const [tab, setTab] = useState('OVERVIEW')
  const [cutView, setCutView] = useState<'PIECE' | 'STOCK'>('PIECE')
  const [params, setParams] = useState<Record<string, any>>(DEFAULT_PARAMS)
  const [assembly, setAssembly] = useState<any>(null)
  const [stockPlan, setStockPlan] = useState<any>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [exporting, setExporting] = useState(false)
  const [sheet, setSheet] = useState(1)
  const [previewVersion, setPreviewVersion] = useState(0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const options = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) }
        const [g, o] = await Promise.all([apiFetch('geometry', options), apiFetch('optimizer', options)])
        if (!g.ok || !o.ok) throw new Error('The fabrication data could not be generated.')
        const [geometry, optimizer] = await Promise.all([g.json(), o.json()])
        if (!cancelled) { setAssembly(geometry); setStockPlan(optimizer); setError('') }
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : 'The backend is not available.') }
    }
    void load()
    return () => { cancelled = true }
  }, [params])

  const failures = useMemo(() => {
    const list: string[] = []
    if (assembly?.structural?.status === 'FAIL') list.push('Load validation failed. Stop and review the fabrication package before building.')
    if (assembly?.geometry_check_report?.overall_status === 'FAIL') list.push('Fit or geometry validation failed. Stop and review the fabrication package before building.')
    return list
  }, [assembly])
  const parts = useMemo(() => (assembly?.bom || []).filter((x: any) => {
    const q = search.trim().toLowerCase()
    return !q || [x.piece_mark, x.description, x.notes].some(v => String(v || '').toLowerCase().includes(q))
  }), [assembly, search])

  const exportPack = async () => {
    setExporting(true)
    try {
      const r = await apiFetch('export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) }, 180_000)
      if (!r.ok) throw new Error()
      const url = URL.createObjectURL(await r.blob()), a = document.createElement('a')
      a.href = url; a.download = 'Z-Spray-Carrier-Fabrication-Package.zip'; document.body.appendChild(a); a.click(); a.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
      setPreviewVersion(Date.now())
    } catch { window.alert('The shop pack could not be exported. Check the backend server and try again.') }
    finally { setExporting(false) }
  }
  const save = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(params, null, 2)], { type: 'application/json' })), a = document.createElement('a')
    a.href = url; a.download = 'z-spray-carrier-project.json'; a.click(); URL.revokeObjectURL(url)
  }
  const loadProject = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file) return
    const reader = new FileReader()
    reader.onload = async e => {
      try {
        const loaded = JSON.parse(String(e.target?.result || ''))
        if (!loaded || Array.isArray(loaded) || typeof loaded !== 'object') throw new Error()
        const merged = { ...params, ...loaded }
        if (!Array.isArray(merged.available_stock_lengths) || !merged.available_stock_lengths.length ||
          merged.available_stock_lengths.some((v: any) => typeof v !== 'number') || typeof merged.saw_kerf !== 'number' || merged.saw_kerf <= 0) throw new Error()
        const check = await apiFetch('geometry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(merged) })
        if (!check.ok) throw new Error()
        setParams(merged)
        const changed = DESIGN_KEYS.some(k => JSON.stringify(merged[k]) !== JSON.stringify(DEFAULT_PARAMS[k]))
        setNotice(changed ? 'NONSTANDARD PROJECT LOADED — dimensions differ from the established carrier.' : 'Project loaded and checked.')
      } catch { window.alert('This is not a valid Z-Spray Carrier project file. The current project was not changed.') }
    }
    reader.readAsText(file)
  }
  const restore = async () => {
    if (!window.confirm('Restore the established carrier project?')) return
    try { const r = await apiFetch('project/seed'); if (!r.ok) throw new Error(); setParams((await r.json()).parameters); setNotice('Established carrier project restored.') }
    catch { window.alert('The established project could not be restored.') }
  }
  const setStock = (choice: string) => setParams(p => ({ ...p, available_stock_lengths: choice === '20' ? [240] : choice === '24' ? [288] : [240, 288] }))
  const setNumber = (key: string, value: string) => setParams(p => ({ ...p, [key]: Number(value) }))
  const stockChoice = params.available_stock_lengths.length > 1 ? 'both' : params.available_stock_lengths[0] === 240 ? '20' : '24'

  return <div className="app-container">
    <header className="app-header">
      <div className="brand-zone"><div className="logo-icon">Z</div><div><h1>Z-Spray Carrier</h1><p>Z-Spray Junior · 2015 F-350</p></div></div>
      <div className="header-actions"><details className="project-file"><summary>Project file</summary><div className="project-file-controls">
        <button className="btn btn-secondary" onClick={save}>Save project</button><label className="btn btn-secondary file-label">Load project<input type="file" accept=".json" onChange={loadProject} hidden /></label><button className="btn btn-secondary" onClick={() => void restore()}>Restore established project</button>
      </div></details><button className="btn btn-primary" onClick={() => void exportPack()} disabled={exporting}>{exporting ? 'PREPARING SHOP PACK…' : 'EXPORT SHOP PACK'}</button></div>
    </header>
    <nav className="primary-nav" aria-label="Shop sections">{[['OVERVIEW','Overview'],['BUILD','Build'],['CUT','Cut List'],['BUY','Buy List'],['DRAWINGS','Drawings']].map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
    <main className="main-content">
      {error && <div className="failure-banner"><strong>FABRICATION DATA UNAVAILABLE</strong><span>{error}</span></div>}
      {failures.map(x => <div className="failure-banner" key={x}><strong>STOP — CHECK REQUIRED</strong><span>{x}</span></div>)}
      {notice && <div className={notice.startsWith('NONSTANDARD') ? 'project-notice warning' : 'project-notice'}>{notice}</div>}

      {tab === 'OVERVIEW' && <section className="panel overview"><div className="eyebrow">ESTABLISHED SHOP BUILD</div><h2>Z-Spray Carrier</h2><p className="lead">Carrier for a <strong>Z-Spray Junior</strong> on a <strong>2015 F-350 flatbed</strong>.</p>
        <div className="orientation"><span>← TRUCK SIDE</span><span>RAMP SIDE →</span></div><div className="dimension-grid"><div><span>USABLE WIDTH</span><strong>{fraction(params.carrier_max_overall_width)}</strong></div><div><span>DECK LENGTH</span><strong>{fraction(params.carrier_deck_length)}</strong></div><div><span>RAMP LENGTH</span><strong>{fraction(params.ramp_length)}</strong></div></div>
        <div className="action-row"><button className="btn btn-secondary" onClick={() => { setSheet(1); setTab('DRAWINGS') }}>View S1 general arrangement</button><button className="btn btn-primary" onClick={() => void exportPack()}>Export Shop Pack</button></div>
        <details className="parameters-panel"><summary>Carrier parameters</summary><p>These values change the generated carrier, checks, lists and drawings. Save the established project before changing them.</p><div className="parameter-grid">
          {PARAMETER_FIELDS.map(([key, label, unit, step]) => <label key={key}><span>{label}</span><div><input type="number" value={params[key]} step={step} onChange={e => setNumber(key, e.target.value)} /><em>{unit}</em></div></label>)}
          <label><span>Stinger section</span><select value={params.stinger_section} onChange={e => setParams(p => ({ ...p, stinger_section: e.target.value }))}><option>2x2x1/4 Tube</option><option>2x2x3/16 Tube</option></select></label>
          <label><span>Fertilizer capacity</span><div><input type="number" value={params.fertilizer_hopper_weight + params.fertilizer_trays_weight} step="1" onChange={e => { const total = Number(e.target.value); setParams(p => ({ ...p, fertilizer_hopper_weight: total * .6, fertilizer_trays_weight: total * .4 })) }} /><em>lb</em></div></label>
        </div></details></section>}

      {tab === 'BUILD' && <section className="panel"><h2>Build</h2><p className="lead">Tack, fit and check before final welding.</p><div className="build-sequence"><h3>Build order</h3><ol>{(assembly?.fabrication_sequence || []).map((x: string, i: number) => <li key={i}>{x}</li>)}</ol></div>
        <div className="piece-lookup"><div><h3>Piece notes</h3><p>Search a piece mark or part name for its fabrication and fit-up note.</p></div><input className="search-input" type="search" aria-label="Search piece notes" placeholder="Example: S1-L or hinge" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <div className="table-scroll"><table className="data-table"><thead><tr><th>Mark</th><th>Part</th><th>Fit / build note</th></tr></thead><tbody>{parts.map((x: any) => <tr key={x.piece_mark} className={fieldFit(x) ? 'field-fit-row' : ''}><td><span className="mark-badge">{x.piece_mark}</span>{fieldFit(x) && <span className="fit-label">CUT TO FIT</span>}</td><td>{x.description}</td><td>{x.notes}</td></tr>)}</tbody></table></div></section>}

      {tab === 'CUT' && <section className="panel"><div className="panel-heading"><div><h2>Cut List</h2><p>Every piece and every stock stick.</p></div><div className="view-switch" aria-label="Cut list view"><button className={cutView === 'PIECE' ? 'active' : ''} onClick={() => setCutView('PIECE')}>By piece</button><button className={cutView === 'STOCK' ? 'active' : ''} onClick={() => setCutView('STOCK')}>By stock stick</button></div></div>
        <details className="cutting-setup"><summary>Cutting setup</summary><div className="setup-grid"><label>Available stock lengths<select value={stockChoice} onChange={e => setStock(e.target.value)}><option value="20">20 ft</option><option value="24">24 ft</option><option value="both">20 ft and 24 ft</option></select></label><label>Saw kerf<select value={params.saw_kerf} onChange={e => setParams(p => ({ ...p, saw_kerf: Number(e.target.value) }))}><option value="0.0625">1/16&quot;</option><option value="0.125">1/8&quot;</option><option value="0.1875">3/16&quot;</option><option value="0.25">1/4&quot;</option></select></label></div></details>
        {cutView === 'PIECE' ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Mark</th><th>Qty</th><th>Material / section</th><th>Cut length</th><th>Essential preparation</th></tr></thead><tbody>{(assembly?.cut_list || []).map((x: any) => <tr key={x.piece_mark} className={fieldFit(x) ? 'field-fit-row' : ''}><td><span className="mark-badge">{x.piece_mark}</span>{fieldFit(x) && <span className="fit-label">CUT TO FIT — APPROX.</span>}</td><td className="quantity-cell">{x.quantity}</td><td>{x.section}</td><td className="cut-length">{fraction(x.cut_length)}</td><td>{prep(x)}</td></tr>)}</tbody></table></div> : <div className="sticks-container">{(stockPlan?.stock_plan || []).map((s: any) => <article className="stick-card" key={s.stick_id}><h3>{s.stick_id} — {s.section} — {s.stock_length / 12} ft stick</h3><div className="stock-cut-label">CUT:</div><ol className="stock-cut-list">{s.parts.map((p: any, i: number) => <li key={`${p.piece_mark}-${i}`} className={fieldFit(p) ? 'stock-field-fit' : ''}><strong>{p.piece_mark}</strong> — {fraction(p.length)} {fieldFit(p) && <span>CUT TO FIT — APPROX.</span>}</li>)}</ol><p className="stock-leftover">LEFT OVER: {fraction(s.scrap_remaining)}</p></article>)}</div>}
      </section>}

      {tab === 'BUY' && <section className="panel"><h2>Buy List</h2><p className="lead">Material and hardware required for this carrier.</p><div className="table-scroll"><table className="data-table buy-table"><thead><tr><th>Material / hardware</th><th>Specification</th><th>Purchase size</th><th>Qty</th></tr></thead><tbody>{(stockPlan?.purchase_list || []).map((x: any, i: number) => <tr key={`${x.section}-${i}`}><td><strong>{x.section}</strong></td><td>{x.grade}</td><td>{x.stick_length ? `${x.stick_length / 12} ft` : x.unit_size}</td><td className="quantity-cell">{x.quantity}</td></tr>)}</tbody></table></div></section>}

      {tab === 'DRAWINGS' && <section className="panel"><div className="panel-heading"><div><h2>Drawings</h2><p>Select a sheet to see the latest generated preview.</p></div><button className="btn btn-primary" onClick={() => void exportPack()}>Export Shop Pack</button></div><div className="sheet-selector">{SHEETS.map((title, i) => <button key={title} className={sheet === i + 1 ? 'selected' : ''} onClick={() => setSheet(i + 1)}><strong>S{i + 1}</strong><span>{title}</span></button>)}</div><h3 className="drawing-title">S{sheet} — {SHEETS[sheet - 1]}</h3><div className="drawing-preview"><img src={`${apiUrl(`drawings/preview/${sheet}`)}?v=${previewVersion}`} alt={`Shop drawing S${sheet}: ${SHEETS[sheet - 1]}`} /></div></section>}
    </main>
  </div>
}
export default App
