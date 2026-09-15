// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import BuyList, { type PurchaseRow } from './BuyList'

afterEach(cleanup)

const optimizerRows: PurchaseRow[] = [
  {
    category: 'LINEAR_STOCK', section: '2x2x3/16 Tube', grade: 'ASTM A500 Gr B',
    stick_length: 240, quantity: 2, unit_size: '20-FT Commercial Stick',
    total_purchased_length: 480, total_purchased_weight: 172.8,
    notes: 'Standard 20 foot mill length.',
  },
  {
    category: 'PLATE', section: '0.25 in steel plate', grade: 'ASTM A36',
    stick_length: 0, quantity: 1, unit_size: '24 x 48 in x 0.25 in steel plate',
    total_purchased_length: 0, total_purchased_weight: 81.7,
    notes: 'Fits the 3 x 36 in ramp transition plate.',
  },
  {
    category: 'GRATING', section: '#9 flattened expanded metal', grade: 'ASTM A36',
    stick_length: 0, quantity: 1, unit_size: '48 x 96 in sheet',
    total_purchased_length: 0, total_purchased_weight: 57.6, notes: 'Deck and ramp traction surface.',
  },
  {
    category: 'HARDWARE', section: '5/8 in hitch pins with retaining clips', grade: 'Grade 8',
    stick_length: 0, quantity: 2, unit_size: 'each', total_purchased_length: 0,
    total_purchased_weight: 1.8, notes: 'One for each truck mounting tube.',
  },
]

test('renders real material purchasing rows and summary from an optimizer response', () => {
  const download = vi.fn()
  render(<BuyList rows={optimizerRows} totalWeight={313.9} loading={false} error=""
    downloading={false} onDownload={download} />)

  expect(screen.getByRole('heading', { name: /Purchase List — Material to Buy/i })).toBeInTheDocument()
  expect(screen.getByText('2x2x3/16 Tube')).toBeInTheDocument()
  expect(screen.getByText('24 x 48 in x 0.25 in steel plate')).toBeInTheDocument()
  expect(screen.getByText('#9 flattened expanded metal')).toBeInTheDocument()
  expect(screen.getByText('5/8 in hitch pins with retaining clips')).toBeInTheDocument()
  expect(screen.getByText('313.9 lb')).toBeInTheDocument()
  expect(screen.getByText('40 ft')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'DOWNLOAD MATERIAL LIST' }))
  expect(download).toHaveBeenCalledOnce()
})

test('fails visibly instead of presenting a blank purchase table', () => {
  render(<BuyList rows={null} totalWeight={0} loading={false}
    error="Material optimizer request failed (404)." downloading={false} onDownload={() => {}} />)
  expect(screen.getByRole('alert')).toHaveTextContent('MATERIAL LIST UNAVAILABLE')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
