import React, { useState, useEffect } from 'react'
import './App.css'

interface ParameterProvenance {
  name: string
  value: number
  units: string
  status: 'MEASURED' | 'OEM' | 'DESIGN' | 'CALCULATED' | 'ESTIMATED_UNVERIFIED'
  description: string
  source_note: string
  required_before_fabrication: boolean
}

function App() {
  const [activeTab, setActiveTab] = useState<string>('CARRIER')
  const [params, setParams] = useState({
    carrier_max_overall_width: 38.0,
    carrier_width: 36.0,
    carrier_deck_length: 63.0,
    deck_height: 17.25,
    track_flat_width: 11.5,
    track_outer_spacing: 36.0,
    track_center_gap: 13.0,
    flared_guide_height: 3.0,
    flare_angle: 45.0,
    flare_width: 1.0,
    ramp_length: 61.0,
    ramp_clearance: 1.0,
    hinge_pin_dia: 0.75,
    hinge_barrel_od: 1.25,
    hinge_barrel_wall: 0.1875,
    hinge_barrel_id: 0.875,
    hinge_barrel_length: 4.0,
    hinge_barrel_count: 7,
    hinge_barrel_gap: 0.5,
    hinge_pin_length: 36.0,
    stinger_spacing_model_nominal: 37.5,
    stinger_section: '2x2x1/4 Tube',
    stinger_sleeve_section: '2.5x2.5x3/16 Tube',
    stinger_sleeve_length: 40.0,
    stinger_insertion_length: 18.0,
    stinger_overlap_length: 40.0,
    mount_beam_section: '2x2x1/4 Tube',
    mount_beam_stations: [4.0, 17.0, 37.0],
    hitch_pin_hole_setback: 3.0,
    hitch_pin_hole_dia: 0.656,
    truck_suspension_drop: 1.5,
    machine_width: 36.0,
    machine_length_oem: 70.5,
    machine_length_field: 72.0,
    machine_height: 48.0,
    machine_curb_weight: 698.0,
    fertilizer_hopper_weight: 150.0,
    fertilizer_trays_weight: 100.0,
    spray_tank_gallons: 24.0,
    liquid_density_lb_gal: 8.34,
    vertical_dynamic_factor: 2.0,
    braking_factor: 0.8,
    lateral_factor: 0.5,
    material_yield_strength: 46000.0,
    target_safety_factor: 2.0,
    available_stock_lengths: [240.0, 288.0],
    saw_kerf: 0.125
  })

  const [assembly, setAssembly] = useState<any>(null)
  const [provenance, setProvenance] = useState<Record<string, ParameterProvenance>>({})
  const [stockPlan, setStockPlan] = useState<any>(null)
  const [isExporting, setIsExporting] = useState<boolean>(false)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [assemblyFilter, setAssemblyFilter] = useState<string>('ALL')

  const fetchProjectData = async () => {
    try {
      const geoRes = await fetch('http://localhost:8000/api/geometry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
      const geoData = await geoRes.json()
      setAssembly(geoData)

      const provRes = await fetch('http://localhost:8000/api/provenance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
      const provData = await provRes.json()
      setProvenance(provData)

      const optRes = await fetch('http://localhost:8000/api/optimizer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
      const optData = await optRes.json()
      setStockPlan(optData)
    } catch (e) {
      console.error('API connection error:', e)
    }
  }

  useEffect(() => {
    fetchProjectData()
  }, [params])

  const handleParamChange = (name: string, val: any) => {
    setParams(prev => ({ ...prev, [name]: typeof val === 'number' ? val : val }))
  }

  const handleExport = async () => {
    setIsExporting(true)
    try {
      const res = await fetch('http://localhost:8000/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'Z-Spray-Carrier-Fabrication-Package.zip'
      a.click()
    } catch (e) {
      alert('Error exporting fabrication package. Check backend server.')
    }
    setIsExporting(false)
  }

  const handleSaveJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(params, null, 2))
    const dlAnchor = document.createElement('a')
    dlAnchor.setAttribute('href', dataStr)
    dlAnchor.setAttribute('download', 'z-spray-carrier-project.json')
    dlAnchor.click()
  }

  const handleLoadJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const loaded = JSON.parse(event.target?.result as string)
        setParams(loaded)
      } catch (err) {
        alert('Invalid project JSON file.')
      }
    }
    reader.readAsText(file)
  }

  const handleResetSeed = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/project/seed')
      const data = await res.json()
      setParams(data.parameters)
    } catch (e) {
      console.error(e)
    }
  }

  const unverifiedList = Object.values(provenance).filter(
    p => p.status === 'ESTIMATED_UNVERIFIED'
  )

  const renderBadge = (status?: string) => {
    if (!status) return null
    const colorClass = `badge-${status.toLowerCase()}`
    return <span className={`status-badge ${colorClass}`}>{status}</span>
  }

  const filteredBom = (assembly?.bom || []).filter((item: any) => {
    const matchesSearch = item.piece_mark.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          item.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          item.size.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesAssy = assemblyFilter === 'ALL' || item.assembly === assemblyFilter
    return matchesSearch && matchesAssy
  })

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-zone">
          <div className="logo-icon">Z</div>
          <div>
            <h1>Z SPRAY CARRIER FABRICATOR</h1>
            <p className="subtitle">Parametric Steel Fabrication & Shop-Drawing Generator (2026 Z-Spray Jr / 2015 F-350)</p>
          </div>
        </div>

        <div className="header-actions">
          <button className="btn btn-secondary" onClick={handleSaveJson}>Save JSON</button>
          <label className="btn btn-secondary file-label">
            Load JSON
            <input type="file" accept=".json" onChange={handleLoadJson} style={{ display: 'none' }} />
          </label>
          <button className="btn btn-secondary" onClick={handleResetSeed}>Reset Seed</button>
          <button className="btn btn-primary export-btn" onClick={handleExport} disabled={isExporting}>
            {isExporting ? 'Generating Package...' : 'Export Fabrication Package (ZIP)'}
          </button>
        </div>
      </header>

      {/* Metric Callout Banner */}
      <div className="metrics-banner">
        <div className="metric-chip">
          <span className="label">MAX OVERALL WIDTH:</span>
          <span className="val">{params.carrier_max_overall_width}" {renderBadge('DESIGN')}</span>
        </div>
        <div className="metric-chip">
          <span className="label">FRAME WIDTH:</span>
          <span className="val">{params.carrier_width}" {renderBadge('DESIGN')}</span>
        </div>
        <div className="metric-chip">
          <span className="label">DECK LENGTH:</span>
          <span className="val">{params.carrier_deck_length}" {renderBadge('MEASURED')}</span>
        </div>
        <div className="metric-chip">
          <span className="label">TRUCK MOUNT:</span>
          <span className="val">FIELD FIT TO TRUCK {renderBadge('FIELD_FIT')}</span>
        </div>
        <div className="metric-chip">
          <span className="label">EST. STEEL DEADWEIGHT:</span>
          <span className="val">{assembly?.total_carrier_weight || '--'} LB</span>
        </div>
        <div className="metric-chip">
          <span className="label">STRUCTURAL STATUS:</span>
          <span className="val">
            {assembly?.structural?.status === 'PASS' ? (
              <span className="status-badge badge-pass">PASS (holds to {assembly.structural.yields_at_g}g)</span>
            ) : (
              <span className="status-badge badge-fail">FAIL (yields at {assembly?.structural?.yields_at_g ?? '--'}g)</span>
            )}
          </span>
        </div>
        <div className="metric-chip alert-chip" onClick={() => setActiveTab('WARNINGS')}>
          <span className="label">UNVERIFIED ITEMS:</span>
          <span className="val alert-val">{unverifiedList.length} FIELD CHECKS REQ'D</span>
        </div>
      </div>

      {/* Main Layout */}
      <div className="workspace-layout">
        {/* Navigation Tabs */}
        <nav className="tab-navigation">
          {[
            { id: 'PROJECT', label: '1. PROJECT' },
            { id: 'CARRIER', label: '2. CARRIER DECK' },
            { id: 'TRACKS', label: '3. TRACKS & GUIDES' },
            { id: 'RAMP', label: '4. RAMP WELDMENT' },
            { id: 'TRUCK', label: '5. TRUCK MOUNTS' },
            { id: 'LOADS', label: '6. MACHINE & LOADS' },
            { id: 'MATERIALS', label: '7. MATERIALS' },
            { id: 'BOM', label: '8. PIECES & BOM' },
            { id: 'CUTLIST', label: '9. CUT LIST' },
            { id: 'STOCKPLAN', label: '10. STOCK PLAN' },
            { id: 'DRAWINGS', label: '11. SHOP DRAWINGS' },
            { id: 'WARNINGS', label: `12. WARNINGS (${unverifiedList.length})` }
          ].map(tab => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''} ${tab.id === 'WARNINGS' ? 'tab-warn' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Dynamic Center Panel */}
        <main className="tab-content-area">
          {/* TAB 1: PROJECT */}
          {activeTab === 'PROJECT' && (
            <div className="panel-box">
              <h2>Project Overview & Seed Baseline</h2>
              <p className="panel-desc">
                Parametric steel fabrication generator configured for a <strong>2026 Z-Spray Junior (Model ZSX3624)</strong> mounted behind a <strong>2015 Ford F-350 Flatbed Truck</strong> using twin rear receiver tubes.
              </p>
              <div className="info-grid">
                <div className="info-card">
                  <h4>Truck Interface</h4>
                  <p>Twin receiver outside-to-outside span: <strong>40.00"</strong></p>
                  <p>Receiver tube outside width: <strong>2.00"</strong></p>
                  <p>Calculated center-to-center spacing: <strong>38.00"</strong> (Fixed datum)</p>
                </div>
                <div className="info-card">
                  <h4>Carrier Baseline</h4>
                  <p>Overall carrier width: <strong>38.00"</strong> (Field proven)</p>
                  <p>Deck length: <strong>63.00"</strong> (Front stop to ramp hinge)</p>
                  <p>Target running deck height: <strong>17.00"</strong> (No sag reproduction)</p>
                </div>
                <div className="info-card">
                  <h4>Rigid Ramp Assembly</h4>
                  <p>Ramp length: <strong>61.00"</strong> hinge centerline to ground tip</p>
                  <p>Hinge configuration: <strong>ONE single rigid hinged weldment</strong></p>
                  <p>Secondary containment: Upright 90-degree transport lock</p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CARRIER DECK */}
          {activeTab === 'CARRIER' && (
            <div className="panel-box">
              <h2>Main Carrier Deck Geometry</h2>
              <div className="form-grid">
                <div className="input-field">
                  <label>Max Overall Width (in) {renderBadge('DESIGN')}</label>
                  <input
                    type="number"
                    value={params.carrier_max_overall_width}
                    disabled
                  />
                  <span className="hint">HARD LIMIT: 38.00" max across flare tips</span>
                </div>
                <div className="input-field">
                  <label>Carrier Frame Width (in) {renderBadge(provenance.carrier_width?.status)}</label>
                  <input
                    type="number"
                    value={params.carrier_width}
                    onChange={e => handleParamChange('carrier_width', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Outside-to-outside of outer longitudinal rails M1 (36.00")</span>
                </div>
                <div className="input-field">
                  <label>Carrier Deck Length (in) {renderBadge(provenance.carrier_deck_length?.status)}</label>
                  <input
                    type="number"
                    value={params.carrier_deck_length}
                    onChange={e => handleParamChange('carrier_deck_length', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Front stop face to primary rear ramp hinge CL</span>
                </div>
                <div className="input-field">
                  <label>Target Deck Running Height (in) {renderBadge(provenance.deck_height?.status)}</label>
                  <input
                    type="number"
                    value={params.deck_height}
                    onChange={e => handleParamChange('deck_height', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Target elevation above road grade</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: TRACKS & GUIDES */}
          {activeTab === 'TRACKS' && (
            <div className="panel-box">
              <h2>Dual Wheel Tracks & Flared Guide Geometry</h2>
              <div className="form-grid">
                <div className="input-field">
                  <label>Flat Track Width (in)</label>
                  <input
                    type="number"
                    value={params.track_flat_width}
                    onChange={e => handleParamChange('track_flat_width', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">11.50" flat width (supports 8.5" rear tires with 3.0" mud slop)</span>
                </div>
                <div className="input-field">
                  <label>Center Cleanout Gap (in)</label>
                  <input
                    type="number"
                    value={params.track_center_gap}
                    disabled
                  />
                  <span className="hint">13.00" clear opening between M2 rails for debris shedding</span>
                </div>
                <div className="input-field">
                  <label>Flared Guide Vertical Rise (in)</label>
                  <input
                    type="number"
                    value={params.flared_guide_height}
                    onChange={e => handleParamChange('flared_guide_height', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">3.00" vertical containment height along outer edges</span>
                </div>
                <div className="input-field">
                  <label>Guide Flare Angle (deg)</label>
                  <input
                    type="number"
                    value={params.flare_angle}
                    onChange={e => handleParamChange('flare_angle', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Outward guide bevel angle (45 deg)</span>
                </div>
                <div className="input-field">
                  <label>Flare Outward Projection (in)</label>
                  <input
                    type="number"
                    value={params.flare_width}
                    onChange={e => handleParamChange('flare_width', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">1.00" per side (36.0" frame + 2x1.0" = 38.00" MAX)</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: RAMP WELDMENT */}
          {activeTab === 'RAMP' && (
            <div className="panel-box">
              <h2>Ramp Weldment & Hinge Parameters</h2>
              <div className="form-grid">
                <div className="input-field">
                  <label>Rigid Ramp Length (in) {renderBadge(provenance.ramp_length?.status)}</label>
                  <input
                    type="number"
                    value={params.ramp_length}
                    onChange={e => handleParamChange('ramp_length', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">61.00" single rigid assembly from hinge CL to tip</span>
                </div>
                <div className="input-field">
                  <label>Rear Tire Clearance to Upright Ramp (in) {renderBadge(provenance.ramp_clearance?.status)}</label>
                  <input
                    type="number"
                    value={params.ramp_clearance}
                    onChange={e => handleParamChange('ramp_clearance', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">1.0" clearance with rear tires at X=51"-62" (ramp at X=63")</span>
                </div>
                <div className="input-field">
                  <label>Hinge Pin Diameter (in)</label>
                  <input
                    type="number"
                    value={params.hinge_pin_dia}
                    onChange={e => handleParamChange('hinge_pin_dia', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">3/4" (0.750") AISI 1018 Cold Finished Round Bar</span>
                </div>
                <div className="input-field">
                  <label>DOM Mechanical Sleeve OD x Wall</label>
                  <input
                    type="text"
                    disabled
                    value={'1-1/8" OD x 0.172" Wall (0.781" ID)'}
                  />
                  <span className="hint">ASTM A513 DOM: 0.031" (1/32") diametral clearance over pin</span>
                </div>
                <div className="input-field">
                  <label>Calculated Deployed Slope (deg)</label>
                  <input
                    type="text"
                    disabled
                    value={`${assembly?.ramp_angle_deg || 16.2} deg`}
                  />
                  <span className="hint">Calculated from 17.0" deck height and 61.0" ramp length</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: TRUCK MOUNTS */}
          {activeTab === 'TRUCK' && (
            <div className="panel-box">
              <h2>Truck Mount - Field Fit</h2>
              <p className="warn-text">
                The truck is the fixture. Slide both mounting tubes into the two
                existing sockets and the spacing sets itself. There is no
                receiver measurement to take and no centreline to calculate.
                Pin holes are transferred from the truck.
              </p>
              <div className="form-grid">
                <div className="input-field">
                  <label>Mounting Tube Section</label>
                  <select
                    value={params.stinger_section}
                    onChange={e => handleParamChange('stinger_section', e.target.value)}
                  >
                    <option value="2x2x1/4 Tube">HSS 2x2x1/4 Tube (Recommended)</option>
                    <option value="2x2x3/16 Tube">HSS 2x2x3/16 Tube</option>
                  </select>
                </div>
                <div className="input-field unverified-field">
                  <label>Mounting Tube Insertion Depth (in) {renderBadge('FIELD_FIT')}</label>
                  <input
                    type="number"
                    value={params.stinger_insertion_length}
                    onChange={e => handleParamChange('stinger_insertion_length', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Nominal only - push the tube in until it stops. FIELD FIT TO TRUCK.</span>
                </div>
                <div className="input-field unverified-field">
                  <label>Hitch Pin Hole Setback (in) {renderBadge('FIELD_FIT')}</label>
                  <input
                    type="number"
                    value={params.hitch_pin_hole_setback}
                    onChange={e => handleParamChange('hitch_pin_hole_setback', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Nominal only - TRANSFER PIN HOLES FROM TRUCK.</span>
                </div>
                <div className="input-field">
                  <label>Mounting Tube Run-Back (in) {renderBadge('DESIGN')}</label>
                  <input
                    type="number"
                    value={params.stinger_overlap_length}
                    onChange={e => handleParamChange('stinger_overlap_length', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">How far the mounting tubes run back under the deck, past all three mount beams</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: LOADS */}
          {activeTab === 'LOADS' && (
            <div className="panel-box">
              <h2>Machine Payloads & Engineering Structural Checks</h2>
              <div className="form-grid">
                <div className="input-field">
                  <label>Z-Spray Curb Weight (lb) {renderBadge('OEM')}</label>
                  <input
                    type="number"
                    value={params.machine_curb_weight}
                    onChange={e => handleParamChange('machine_curb_weight', parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="input-field">
                  <label>Fertilizer Capacity (lb) {renderBadge('OEM')}</label>
                  <input
                    type="number"
                    value={params.fertilizer_hopper_weight + params.fertilizer_trays_weight}
                    onChange={e => {
                      const v = parseFloat(e.target.value) || 0
                      handleParamChange('fertilizer_hopper_weight', v * 0.6)
                      handleParamChange('fertilizer_trays_weight', v * 0.4)
                    }}
                  />
                </div>
                <div className="input-field">
                  <label>Spray Tank Capacity (gal) {renderBadge('OEM')}</label>
                  <input
                    type="number"
                    value={params.spray_tank_gallons}
                    onChange={e => handleParamChange('spray_tank_gallons', parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div className="input-field">
                  <label>Vertical Dynamic Factor (g)</label>
                  <input
                    type="number"
                    value={params.vertical_dynamic_factor}
                    onChange={e => handleParamChange('vertical_dynamic_factor', parseFloat(e.target.value) || 0)}
                  />
                  <span className="hint">Bump / rough road factor (2.0g standard)</span>
                </div>
              </div>

              {assembly?.structural && (
                <div className="structural-summary">
                  {assembly.structural.status === 'FAIL' ? (
                    <div className="structural-fail-banner">
                      <h3>NOT STRONG ENOUGH: yields at about {assembly.structural.yields_at_g}g (needs {assembly.structural.target_safety_factor}g)</h3>
                      <p>
                        Mounting tube bending is {Math.round(assembly.structural.stinger_bending_stress_psi).toLocaleString()} psi against {Math.round(assembly.structural.yield_strength_psi).toLocaleString()} psi yield. Fix it on the carrier - the truck does not get modified.
                        DO NOT deploy on public highways without the structural reinforcements listed below.
                      </p>
                    </div>
                  ) : (
                    <div className="alert-box-success" style={{ padding: '12px 16px', marginBottom: '14px' }}>
                      <strong>STRONG ENOUGH: nothing yields below about {assembly.structural.yields_at_g}g</strong>
                    </div>
                  )}

                  <h3>Multi-Case Structural Stress Analysis</h3>
                  <table className="data-table" style={{ marginTop: '8px', marginBottom: '16px' }}>
                    <thead>
                      <tr>
                        <th>Load Case</th>
                        <th>Dynamic Factor</th>
                        <th>Dynamic Load</th>
                        <th>Per-Stinger Moment</th>
                        <th>Bending Stress</th>
                        <th>Safety Factor</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assembly.structural.load_cases && Object.entries(assembly.structural.load_cases).map(([key, lc]: [string, any]) => (
                        <tr key={key} style={key === assembly.structural.controlling_load_case ? { backgroundColor: '#FFF5F5', fontWeight: 'bold' } : {}}>
                          <td><strong>{key} {key === assembly.structural.controlling_load_case && '(GOVERNING)'}</strong></td>
                          <td>{lc.description}</td>
                          <td>{Math.round(lc.load_lb).toLocaleString()} lb</td>
                          <td>{Math.round(lc.per_stinger_moment_in_lb).toLocaleString()} in-lb</td>
                          <td>{Math.round(lc.stinger_stress_psi).toLocaleString()} psi</td>
                          <td><strong>{lc.factor_of_safety}</strong> (target {lc.target_fos})</td>
                          <td>
                            <span className={`status-badge ${lc.status === 'PASS' ? 'badge-pass' : 'badge-fail'}`}>
                              {lc.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {assembly.structural.hinge_check && (
                    <>
                      <h3>Ramp Hinge Check</h3>
                      <table className="data-table" style={{ marginTop: '8px', marginBottom: '16px' }}>
                        <thead>
                          <tr>
                            <th>What is checked</th>
                            <th>Design</th>
                            <th>Stress</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td><strong>Pin running clearance</strong></td>
                            <td>
                              {assembly.structural.hinge_check.pin_diameter_in}" pin in a{' '}
                              {assembly.structural.hinge_check.barrel_id_in}" bore
                            </td>
                            <td>{assembly.structural.hinge_check.diametral_clearance_in}" loose - no reaming</td>
                            <td><span className="status-badge badge-pass">{assembly.structural.hinge_check.clearance_status}</span></td>
                          </tr>
                          <tr>
                            <td><strong>Hinge pin shear</strong></td>
                            <td>
                              {Math.round(assembly.structural.hinge_check.design_load_lb).toLocaleString()} lb over{' '}
                              {assembly.structural.hinge_check.shear_planes} shear planes
                            </td>
                            <td>{Math.round(assembly.structural.hinge_check.pin_shear_stress_psi).toLocaleString()} psi</td>
                            <td><span className="status-badge badge-pass">{assembly.structural.hinge_check.pin_shear_status}</span></td>
                          </tr>
                          <tr>
                            <td><strong>Rear cross tube (C4)</strong></td>
                            <td>{assembly.structural.hinge_check.barrel_count} barrels of {assembly.structural.hinge_check.barrel_od_in}" OD tube</td>
                            <td>{Math.round(assembly.structural.hinge_check.cross_tube_stress_psi).toLocaleString()} psi</td>
                            <td><span className="status-badge badge-pass">{assembly.structural.hinge_check.cross_tube_status}</span></td>
                          </tr>
                          <tr>
                            <td><strong>Barrel welds</strong></td>
                            <td>
                              {Math.round(assembly.structural.hinge_check.weld_demand_lb_per_barrel).toLocaleString()} lb per barrel
                            </td>
                            <td>
                              carries {Math.round(assembly.structural.hinge_check.weld_capacity_lb_per_barrel).toLocaleString()} lb
                            </td>
                            <td><span className="status-badge badge-pass">{assembly.structural.hinge_check.weld_status}</span></td>
                          </tr>
                        </tbody>
                      </table>
                    </>
                  )}

                  {assembly.structural.reinforcement_recommendations && assembly.structural.reinforcement_recommendations.length > 0 && (
                    <div className="recom-box">
                      <h4>Notes on the mounting tubes:</h4>
                      <ul>
                        {assembly.structural.reinforcement_recommendations.map((rec: string, idx: number) => (
                          <li key={idx}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <h3 style={{ marginTop: '16px' }}>Engineering Calculation Notes</h3>
                  <ul className="results-list">
                    {assembly.structural.notes.map((note: string, idx: number) => (
                      <li key={idx}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* TAB 7: MATERIALS */}
          {activeTab === 'MATERIALS' && (
            <div className="panel-box">
              <h2>Central Material & Shape Library</h2>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Section Name</th>
                    <th>Category</th>
                    <th>Grade</th>
                    <th>Unit Weight</th>
                    <th>Yield Strength</th>
                    <th>Primary Usage</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong>2x2x3/16 Tube</strong></td>
                    <td>HSS</td>
                    <td>ASTM A500 Gr B</td>
                    <td>4.32 lb/ft</td>
                    <td>46,000 psi</td>
                    <td>M1 outer rails, C1-C4 crossmembers, R1 ramp tubes</td>
                  </tr>
                  <tr>
                    <td><strong>2x2x1/4 Tube</strong></td>
                    <td>HSS</td>
                    <td>ASTM A500 Gr B</td>
                    <td>5.41 lb/ft</td>
                    <td>46,000 psi</td>
                    <td>S1-L / S1-R truck mounting stingers</td>
                  </tr>
                  <tr>
                    <td><strong>2x2x3/16 Angle</strong></td>
                    <td>Angle</td>
                    <td>ASTM A36</td>
                    <td>2.44 lb/ft</td>
                    <td>36,000 psi</td>
                    <td>M2 & R2 inner track rails, RC1-RC5 ramp crossmembers</td>
                  </tr>
                  <tr>
                    <td><strong>2x2x1/4 Angle</strong></td>
                    <td>Angle</td>
                    <td>ASTM A36</td>
                    <td>3.19 lb/ft</td>
                    <td>36,000 psi</td>
                    <td>G5 front wheel stop chock angles</td>
                  </tr>
                  <tr>
                    <td><strong>1/4" Plate</strong></td>
                    <td>Plate</td>
                    <td>ASTM A36</td>
                    <td>10.2 lb/sqft</td>
                    <td>36,000 psi</td>
                    <td>G1 stinger reinforcement gussets, RF1 ground foot plate</td>
                  </tr>
                  <tr>
                    <td><strong>3/16" Plate</strong></td>
                    <td>Plate</td>
                    <td>ASTM A36</td>
                    <td>7.66 lb/sqft</td>
                    <td>36,000 psi</td>
                    <td>FG1 & RFG1 flared guides, G2 rear light guards</td>
                  </tr>
                  <tr>
                    <td><strong>3/8" Plate</strong></td>
                    <td>Plate</td>
                    <td>ASTM A36</td>
                    <td>15.3 lb/sqft</td>
                    <td>36,000 psi</td>
                    <td>G3 hinge ears, G4 front chain tie-down bracket</td>
                  </tr>
                  <tr>
                    <td><strong>3/4" Round Bar</strong></td>
                    <td>Bar</td>
                    <td>AISI 1018 CF</td>
                    <td>1.50 lb/ft</td>
                    <td>54,000 psi</td>
                    <td>P1 main ramp hinge pivot pin</td>
                  </tr>
                  <tr>
                    <td><strong>1-1/8" OD DOM Tube</strong></td>
                    <td>Round Tube</td>
                    <td>ASTM A513 DOM</td>
                    <td>1.88 lb/ft</td>
                    <td>60,000 psi</td>
                    <td>HS1-HS4 mechanical hinge sleeves</td>
                  </tr>
                  <tr>
                    <td><strong>#9 1-1/2" Expanded Metal</strong></td>
                    <td>Grating</td>
                    <td>ASTM A36</td>
                    <td>1.80 lb/sqft</td>
                    <td>36,000 psi</td>
                    <td>EM1 & REM1 wheel track traction surface</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 8: PIECES & BOM */}
          {activeTab === 'BOM' && (
            <div className="panel-box">
              <div className="panel-header-row">
                <h2>Bill of Materials & Fabrication Piece Schedule</h2>
                <div className="filter-controls">
                  <input
                    type="text"
                    placeholder="Search mark or desc..."
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    className="search-input"
                  />
                  <select
                    value={assemblyFilter}
                    onChange={e => setAssemblyFilter(e.target.value)}
                    className="select-input"
                  >
                    <option value="ALL">All Assemblies</option>
                    <option value="MAIN_CARRIER">Main Carrier</option>
                    <option value="RAMP">Ramp Assembly</option>
                    <option value="STINGER">Truck Stingers</option>
                    <option value="HINGE">Hinge Details</option>
                    <option value="DETAILS">Fabricated Plates</option>
                  </select>
                </div>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mark</th>
                    <th>Description</th>
                    <th>Assy</th>
                    <th>Size / Section</th>
                    <th>Grade</th>
                    <th>Cut Length</th>
                    <th>Qty</th>
                    <th>Unit Wt</th>
                    <th>Total Wt</th>
                    <th>Shop Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBom.map((item: any, idx: number) => (
                    <tr key={idx}>
                      <td><span className="mark-badge">{item.piece_mark}</span></td>
                      <td>{item.description}</td>
                      <td>{item.assembly}</td>
                      <td>{item.size}</td>
                      <td>{item.grade}</td>
                      <td>{item.cut_length ? `${item.cut_length}"` : '--'}</td>
                      <td>{item.quantity}</td>
                      <td>{item.unit_weight}</td>
                      <td><strong>{item.total_weight} lb</strong></td>
                      <td className="note-cell">{item.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 9: CUT LIST */}
          {activeTab === 'CUTLIST' && (
            <div className="panel-box">
              <h2>Shop-Oriented Cut List</h2>
              <p className="panel-desc">All cuts grouped by raw stock with cut angles and end preparations.</p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Mark</th>
                    <th>Raw Section</th>
                    <th>Cut Length</th>
                    <th>Qty</th>
                    <th>End Cut Left</th>
                    <th>End Cut Right</th>
                    <th>Fabrication Cut Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {(assembly?.cut_list || []).map((c: any, i: number) => (
                    <tr key={i}>
                      <td><span className="mark-badge">{c.piece_mark}</span></td>
                      <td>{c.section}</td>
                      <td><strong>{c.cut_length}"</strong></td>
                      <td>{c.quantity}</td>
                      <td>{c.cut_angle_left === 0 ? 'Square (90°)' : `${c.cut_angle_left}° Miter`}</td>
                      <td>{c.cut_angle_right === 0 ? 'Square (90°)' : `${c.cut_angle_right}° Bevel`}</td>
                      <td>{c.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 10: STOCK PLAN */}
          {activeTab === 'STOCKPLAN' && (
            <div className="panel-box">
              <h2>1D Stock Cutting Plan & Material Optimization</h2>
              <div className="nesting-summary">
                <p>Total Raw Steel Weight: <strong>{stockPlan?.total_purchased_weight || 0} lb</strong></p>
                <p>Total Cut Piece Weight: <strong>{stockPlan?.total_cut_weight || 0} lb</strong></p>
                <p>Overall Material Nesting Yield: <strong>{stockPlan?.overall_efficiency_pct || 0}%</strong></p>
              </div>

              <h3>Ordered Raw Stock Sticks</h3>
              <div className="sticks-container">
                {(stockPlan?.stock_plan || []).map((stick: any, i: number) => (
                  <div key={i} className="stick-card">
                    <div className="stick-header">
                      <strong>{stick.stick_id}: {stick.section}</strong> ({stick.stock_length / 12} ft stick - {stick.stock_length}")
                      <span className="stick-stat">Yield: {stick.efficiency_pct}% | Scrap: {stick.scrap_remaining}"</span>
                    </div>
                    <div className="stick-bar-visual">
                      {stick.parts.map((p: any, pi: number) => (
                        <div
                          key={pi}
                          className="stick-part"
                          style={{ width: `${(p.length / stick.stock_length) * 100}%` }}
                          title={`${p.piece_mark}: ${p.length}"`}
                        >
                          {p.piece_mark} ({p.length}")
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 11: DRAWINGS */}
          {activeTab === 'DRAWINGS' && (
            <div className="panel-box">
              <h2>Vector Shop Drawing Set (9 US Letter Sheets)</h2>
              <p className="panel-desc">
                Fully dimensioned multi-sheet vector PDF package generated specifically for US Letter 8.5 x 11 Landscape.
              </p>
              <div className="drawing-sheet-list">
                {[
                  { num: 'S1', title: 'GENERAL ARRANGEMENT', desc: 'Plan, Elevation, Rear, Machine Footprint, 1" Clearance' },
                  { num: 'S2', title: 'MAIN CARRIER WELDMENT - PLAN', desc: 'Steel layout, all crossmembers baseline dimensioned from X=0' },
                  { num: 'S3', title: 'MAIN CARRIER WELDMENT - ELEVATION', desc: 'Side profile, Z datums, stinger underframe connection, Sections' },
                  { num: 'S4', title: 'TWIN RECEIVER / STINGER ASSEMBLY', desc: '38" c-c spacing, stinger section, UNVERIFIED insertion & pin' },
                  { num: 'S5', title: 'RAMP WELDMENT - PLAN', desc: '61" length, dual wheel tracks, RC1-RC5 baseline dims from hinge' },
                  { num: 'S6', title: 'RAMP ELEVATION & HINGE DETAIL', desc: 'Deployed 16.2° angle, upright position, 3/4" pin & DOM sleeves' },
                  { num: 'S7', title: 'INDIVIDUAL FABRICATED PARTS', desc: 'Gussets G1, light guards G2, hinge ears G3, chain tie-down G4' },
                  { num: 'S8', title: 'BILL OF MATERIALS & SCHEDULE', desc: 'Full tabular piece schedule with cut sizes, grades, weights' },
                  { num: 'S9', title: 'STOCK CUTTING PLAN', desc: '1D linear nesting diagrams for raw steel ordering' }
                ].map(s => (
                  <div key={s.num} className="sheet-row">
                    <span className="sheet-num-badge">{s.num}</span>
                    <div className="sheet-info">
                      <h4>{s.title}</h4>
                      <p>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="drawings-action-row">
                <button className="btn btn-primary" onClick={handleExport}>Download Full 9-Sheet PDF Package</button>
              </div>
            </div>
          )}

          {/* TAB 12: WARNINGS */}
          {activeTab === 'WARNINGS' && (
            <div className="panel-box warn-panel">
              <h2>Mandatory Field Verification Warnings</h2>
              <p className="panel-desc">
                The following critical dimensions are currently provisional design estimates. A steel fitter must confirm these on the physical truck and equipment before cutting raw steel:
              </p>
              <div className="unverified-cards">
                {unverifiedList.map(item => (
                  <div key={item.name} className="warn-card">
                    <div className="warn-header">
                      <span className="warn-title">FIELD VERIFICATION: {item.name.toUpperCase()}</span>
                      <span className="warn-badge">REQUIRED BEFORE FABRICATION</span>
                    </div>
                    <p className="warn-desc">{item.description}</p>
                    <p className="warn-action"><strong>Required Action:</strong> {item.source_note}</p>
                    <p className="warn-cur">Provisional Value: <strong>{item.value} {item.units}</strong></p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Real-time 2D Orthographic SVG Preview Sidebar */}
        <aside className="preview-sidebar">
          <div className="preview-header">
            <h3>2D Fabrication Geometry Preview</h3>
            <span className="preview-sub">True Parametric Lines</span>
          </div>

          {/* Plan View Preview */}
          <div className="svg-box">
            <h4>Plan View (X-Y Plane)</h4>
            <svg width="100%" height="220" viewBox="-30 -35 150 70">
              {/* Front Datum Line */}
              <line x1="0" y1="-30" x2="0" y2="30" stroke="#D90429" strokeWidth="0.8" strokeDasharray="2,2" />
              <text x="0" y="-31" fontSize="3" fill="#D90429" textAnchor="middle">X=0</text>

              {/* Truck Stingers (-X) */}
              <rect x="-18" y="-20" width="32" height="2" fill="#CED4DA" stroke="#333" strokeWidth="0.5" />
              <rect x="-18" y="18" width="32" height="2" fill="#CED4DA" stroke="#333" strokeWidth="0.5" />
              {/* Hitch pin holes */}
              <circle cx="-15" cy="-19" r="0.8" fill="#D90429" />
              <circle cx="-15" cy="19" r="0.8" fill="#D90429" />

              {/* Carrier Outer Rails (M1) */}
              <rect x="0" y="-19" width={params.carrier_deck_length} height="2" fill="#DEE2E6" stroke="#000" strokeWidth="0.8" />
              <rect x="0" y="17" width={params.carrier_deck_length} height="2" fill="#DEE2E6" stroke="#000" strokeWidth="0.8" />

              {/* Inner Track Rails (M2) */}
              <rect x="0" y="-9" width={params.carrier_deck_length} height="2" fill="#E9ECEF" stroke="#555" strokeWidth="0.5" />
              <rect x="0" y="7" width={params.carrier_deck_length} height="2" fill="#E9ECEF" stroke="#555" strokeWidth="0.5" />

              {/* Crossmembers C1-C4 */}
              <rect x="0" y="-17" width="2" height="34" fill="#ADB5BD" stroke="#333" strokeWidth="0.5" />
              <rect x="17" y="-17" width="2" height="34" fill="#ADB5BD" stroke="#333" strokeWidth="0.5" />
              <rect x="37" y="-17" width="2" height="34" fill="#ADB5BD" stroke="#333" strokeWidth="0.5" />
              <rect x="61" y="-17" width="2" height="34" fill="#ADB5BD" stroke="#333" strokeWidth="0.5" />

              {/* Ramp Deployed (+X) */}
              <rect x={params.carrier_deck_length} y="-19" width={params.ramp_length} height="2" fill="#A2D2FF" stroke="#0077B6" strokeWidth="0.6" strokeDasharray="1,1" />
              <rect x={params.carrier_deck_length} y="17" width={params.ramp_length} height="2" fill="#A2D2FF" stroke="#0077B6" strokeWidth="0.6" strokeDasharray="1,1" />

              {/* Hinge Line */}
              <line x1={params.carrier_deck_length} y1="-25" x2={params.carrier_deck_length} y2="25" stroke="#D90429" strokeWidth="0.8" strokeDasharray="2,2" />
            </svg>
          </div>

          {/* Elevation View Preview */}
          <div className="svg-box">
            <h4>Elevation View (X-Z Profile)</h4>
            <svg width="100%" height="180" viewBox="-30 -70 150 80">
              {/* Ground Line */}
              <line x1="-25" y1="0" x2="110" y2="0" stroke="#6C757D" strokeWidth="0.8" />
              <text x="-20" y="6" fontSize="3" fill="#6C757D">GROUND (Z=-17")</text>

              {/* Carrier Frame */}
              <rect x="0" y="-17" width={params.carrier_deck_length} height="2" fill="#DEE2E6" stroke="#000" strokeWidth="0.8" />
              {/* Flared Guide */}
              <rect x="0" y="-20" width={params.carrier_deck_length} height="3" fill="#ADB5BD" stroke="#333" strokeWidth="0.5" />

              {/* Stinger */}
              <rect x="-18" y="-19" width="32" height="2" fill="#CED4DA" stroke="#333" strokeWidth="0.5" />

              {/* Upright Ramp (90 deg) */}
              <rect x={params.carrier_deck_length - 2} y={-17 - params.ramp_length} width="2" height={params.ramp_length} fill="#CED4DA" stroke="#333" strokeWidth="0.6" />
              <text x={params.carrier_deck_length + 2} y={-17 - params.ramp_length/2} fontSize="3" fill="#333">UPRIGHT (90°)</text>

              {/* Deployed Ramp Line */}
              <line x1={params.carrier_deck_length} y1="-17" x2={params.carrier_deck_length + 58.5} y2="0" stroke="#0077B6" strokeWidth="1" strokeDasharray="2,2" />
            </svg>
          </div>
        </aside>
      </div>
    </div>
  )
}

export default App
