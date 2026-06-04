// Available locomotives by type with their list price (rule Promotionstabellen).
import React from 'react'

import { TIER_TO_TRAIN, TRAIN_ORDER } from '../constants'

interface TrainPoolProps {
  trainPrices: Record<string, number>
  availableTrains: Record<string, number> // integer tier (as string) → count
}

export function TrainPool({ trainPrices, availableTrains }: TrainPoolProps): React.ReactElement {
  // Map integer-tier counts onto canonical train ids.
  const countByTrain: Record<string, number> = {}
  for (const [tier, count] of Object.entries(availableTrains)) {
    const trainId = TIER_TO_TRAIN[Number(tier)]
    if (trainId) countByTrain[trainId] = count
  }

  return (
    <div className="train-pool" data-testid="train-pool">
      <h2>Loks</h2>
      <table>
        <thead>
          <tr>
            <th>Typ</th>
            <th>Preis</th>
            <th>Verfügbar</th>
          </tr>
        </thead>
        <tbody>
          {TRAIN_ORDER.map((train) => (
            <tr key={train} data-testid={`train-${train}`}>
              <td>{train}</td>
              <td>{trainPrices[train] ?? '—'} M</td>
              <td>{countByTrain[train] ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
