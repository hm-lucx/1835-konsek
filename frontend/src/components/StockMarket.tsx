// Aktienkurstafel. Companies sharing a price field are stacked in the order the
// server delivers in `share_price_order` (top = operates first, rule 5.3.4).
import React from 'react'

import type { StocksState } from '../api/types'
import { SHARE_PRICE_TRACK } from '../constants'

interface StockMarketProps {
  stocks: StocksState
}

export function StockMarket({ stocks }: StockMarketProps): React.ReactElement {
  return (
    <div className="stock-market" data-testid="stock-market">
      <h2>Aktienkurstafel</h2>
      <div className="stock-track">
        {SHARE_PRICE_TRACK.map((price) => {
          const stacked = stocks.share_price_order[String(price)] ?? []
          return (
            <div key={price} className="stock-field" data-price={price}>
              <span className="stock-price">{price}</span>
              <div className="stock-stack" data-testid={`stack-${price}`}>
                {stacked.map((companyId, index) => (
                  <span
                    key={companyId}
                    className="stock-marker"
                    data-company={companyId}
                    data-stack-index={index}
                    style={{ marginTop: index === 0 ? 0 : -10, zIndex: stacked.length - index }}
                  >
                    {companyId}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
