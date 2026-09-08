import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [params, setParams] = useState({
    carrier_width: 38.0,
    carrier_deck_length: 63.0,
    deck_height: 17.0,
    ramp_length: 61.0,
    ramp_clearance: 1.0,
    receiver_spacing: 38.0,
    receiver_height: 17.0,
    machine_width: 36.0,
    machine_length: 70.5,
    machine_weight: 698.0,
    flared_guide_height: 3.0,
    flare_angle: 45.0,
    flare_width: 1.5
  })
  
  const [bom, setBom] = useState([])
  const [isExporting, setIsExporting] = useState(false)

  const fetchGeometry = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/geometry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
      const data = await res.json()
      setBom(data.bom)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchGeometry()
  }, [params])

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
      console.error(e)
    }
    setIsExporting(false)
  }

  const handleChange = (e: any) => {
    setParams({ ...params, [e.target.name]: parseFloat(e.target.value) || 0 })
  }

  return (
    <div className="container">
      <header>
        <h1>Z Spray Carrier Fabricator</h1>
      </header>
      <div className="main-content">
        <div className="sidebar">
          <h3>Parameters (inches)</h3>
          <div className="param-group">
            <label>Carrier Deck Length</label>
            <input type="number" name="carrier_deck_length" value={params.carrier_deck_length} onChange={handleChange} />
          </div>
          <div className="param-group">
            <label>Carrier Overall Width</label>
            <input type="number" name="carrier_width" value={params.carrier_width} onChange={handleChange} />
          </div>
          <div className="param-group">
            <label>Ramp Length</label>
            <input type="number" name="ramp_length" value={params.ramp_length} onChange={handleChange} />
          </div>
          <div className="param-group">
            <label>Machine Clearance</label>
            <input type="number" name="ramp_clearance" value={params.ramp_clearance} onChange={handleChange} />
          </div>
          
          <button className="export-btn" onClick={handleExport} disabled={isExporting}>
            {isExporting ? 'Exporting...' : 'Export Fabrication Package'}
          </button>
        </div>
        
        <div className="preview">
          <h3>BOM Preview</h3>
          <table>
            <thead>
              <tr>
                <th>Mark</th>
                <th>Desc</th>
                <th>Material</th>
                <th>Length</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              {bom.map((item: any, i) => (
                <tr key={i}>
                  <td>{item.mark}</td>
                  <td>{item.description}</td>
                  <td>{item.material}</td>
                  <td>{item.cut_length}</td>
                  <td>{item.quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
          
          <div className="svg-preview">
            <h3>Plan View (Schematic)</h3>
            <svg width="100%" height="300" viewBox="0 0 100 100">
              <rect x={(100 - params.carrier_width)/2} y={10} width={params.carrier_width} height={params.carrier_deck_length} fill="none" stroke="blue" strokeWidth="1" />
              <text x="50" y="50" fontSize="4" textAnchor="middle" fill="blue">Carrier Deck</text>
            </svg>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
