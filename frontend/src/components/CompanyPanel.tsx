import React from 'react'

import type { CompanyState } from '../api/types'
import { TIER_TO_TRAIN } from '../constants'

interface CompanyPanelProps {
  companies: CompanyState[]
}

export function CompanyPanel({ companies }: CompanyPanelProps): React.ReactElement {
  return (
    <div className="company-panel" data-testid="company-panel">
      <h2>Gesellschaften</h2>
      {companies.map((company) => (
        <div
          key={company.id}
          className={`company-card company-card--${company.status}`}
          data-testid={`company-${company.id}`}
        >
          <div className="company-card__head">
            <strong>{company.name}</strong>
            <span className="company-status">{company.status}</span>
          </div>
          <div className="company-card__meta">
            Kasse: {company.treasury} M · Kurs: {company.share_price} M
          </div>
          <div className="company-card__meta">
            Direktor: {company.director_id ?? '—'}
          </div>
          {company.trains.length > 0 && (
            <div className="company-trains">
              Loks: {company.trains.map((t) => TIER_TO_TRAIN[t.tier] ?? t.tier).join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
