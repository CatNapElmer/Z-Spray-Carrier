export type PurchaseRow = {
  category: 'LINEAR_STOCK' | 'PLATE' | 'GRATING' | 'HARDWARE' | string
  section: string
  grade: string
  stick_length: number
  quantity: number
  unit_size: string
  total_purchased_length: number
  total_purchased_weight: number
  notes: string
}

type Props = {
  rows: PurchaseRow[] | null
  totalWeight: number
  loading: boolean
  error: string
  downloading: boolean
  onDownload: () => void
}

const categoryLabel = (category: string) => ({
  LINEAR_STOCK: 'Steel stock',
  PLATE: 'Plate',
  GRATING: 'Expanded metal',
  HARDWARE: 'Hardware',
}[category] || category.replaceAll('_', ' '))

const lengthLabel = (inches: number) => inches > 0 ? `${inches / 12} ft` : '—'

export default function BuyList({ rows, totalWeight, loading, error, downloading, onDownload }: Props) {
  const stockSticks = rows?.filter(row => row.category === 'LINEAR_STOCK')
    .reduce((sum, row) => sum + row.quantity, 0) || 0
  const platePieces = rows?.filter(row => row.category === 'PLATE')
    .reduce((sum, row) => sum + row.quantity, 0) || 0
  const expandedSheets = rows?.filter(row => row.category === 'GRATING')
    .reduce((sum, row) => sum + row.quantity, 0) || 0
  const hardwareLines = rows?.filter(row => row.category === 'HARDWARE').length || 0

  return <section className="panel buy-list-panel">
    <div className="panel-heading buy-heading">
      <div>
        <div className="eyebrow">AUTHORITATIVE PROCUREMENT LIST</div>
        <h2>Purchase List — Material to Buy</h2>
        <p>Buy these commercial stock sizes, sheets and hardware before fabrication.</p>
      </div>
      <button className="btn btn-primary" onClick={onDownload} disabled={downloading || loading || !rows?.length}>
        {downloading ? 'PREPARING CSV…' : 'DOWNLOAD MATERIAL LIST'}
      </button>
    </div>

    {loading && <div className="buy-status" role="status">Calculating material purchases…</div>}
    {!loading && error && <div className="buy-error" role="alert">
      <strong>MATERIAL LIST UNAVAILABLE</strong>
      <span>{error}</span>
      <span>No blank list has been substituted. Check the backend connection and try again.</span>
    </div>}
    {!loading && !error && rows && rows.length === 0 && <div className="buy-error" role="alert">
      <strong>MATERIAL LIST IS EMPTY</strong>
      <span>The optimizer returned no purchasing rows for this carrier.</span>
    </div>}

    {!loading && !error && rows && rows.length > 0 && <>
      <div className="purchase-summary" aria-label="Purchase summary">
        <div><span>Steel stock sticks</span><strong>{stockSticks}</strong></div>
        <div><span>Plate pieces / sheets</span><strong>{platePieces}</strong></div>
        <div><span>Expanded metal sheets</span><strong>{expandedSheets}</strong></div>
        <div><span>Hardware line items</span><strong>{hardwareLines}</strong></div>
        <div><span>Approx. purchased weight</span><strong>{totalWeight.toFixed(1)} lb</strong></div>
      </div>

      <div className="table-scroll buy-table-wrap">
        <table className="data-table buy-table">
          <thead><tr>
            <th>Category</th><th>Material / item</th><th>Grade / specification</th>
            <th>Purchase size</th><th>Qty</th><th>Total purchased length</th>
            <th>Approx. purchased weight</th><th>Purchasing notes</th>
          </tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.category}-${row.section}-${row.stick_length}-${index}`}>
            <td data-label="Category"><span className={`category-badge category-${row.category.toLowerCase()}`}>{categoryLabel(row.category)}</span></td>
            <td data-label="Material / item"><strong>{row.section}</strong></td>
            <td data-label="Grade / specification">{row.grade || '—'}</td>
            <td data-label="Purchase size">{row.unit_size || lengthLabel(row.stick_length)}</td>
            <td data-label="Quantity" className="quantity-cell">{row.quantity}</td>
            <td data-label="Total purchased length">{lengthLabel(row.total_purchased_length)}</td>
            <td data-label="Approx. purchased weight">{row.total_purchased_weight.toFixed(1)} lb</td>
            <td data-label="Purchasing notes">{row.notes || '—'}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </>}
  </section>
}
