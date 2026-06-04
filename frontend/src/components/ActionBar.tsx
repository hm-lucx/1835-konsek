// Renders exactly the actions the server lists in legal_actions (no client-side
// rule logic). Board-targeted actions are "armed" so the player then clicks a
// hex on the map; all other actions submit immediately.
import React from 'react'

import type { Action, LegalActionsResponse } from '../api/types'

const MAP_ACTIONS = new Set([
  'lay_tile',
  'upgrade_tile',
  'place_station',
  'choose_baden_home_station',
])

interface ActionBarProps {
  legalActions: LegalActionsResponse | null
  armedMapAction: string | null
  onSubmit: (action: Action) => void
  onArmMapAction: (actionType: string | null) => void
}

function label(action: Action): string {
  const detail = Object.entries(action)
    .filter(([key]) => key !== 'type')
    .map(([, value]) => String(value))
    .join(' ')
  return detail ? `${action.type} ${detail}` : action.type
}

export function ActionBar({
  legalActions,
  armedMapAction,
  onSubmit,
  onArmMapAction,
}: ActionBarProps): React.ReactElement {
  const actions = legalActions?.actions ?? []

  return (
    <div className="action-bar" data-testid="action-bar">
      <div className="action-bar__phase">
        Phase: {legalActions?.phase ?? '—'}
        {legalActions?.or_phase ? ` · ${legalActions.or_phase}` : ''}
      </div>
      <div className="action-bar__buttons">
        {actions.length === 0 && <span className="action-bar__empty">Keine Aktionen</span>}
        {actions.map((action, index) => {
          const isMap = MAP_ACTIONS.has(action.type)
          const armed = isMap && armedMapAction === action.type
          return (
            <button
              key={`${action.type}-${index}`}
              type="button"
              className={`action-btn${armed ? ' action-btn--armed' : ''}`}
              data-testid={`action-${action.type}`}
              data-action-type={action.type}
              onClick={() => {
                if (isMap) {
                  onArmMapAction(armed ? null : action.type)
                } else {
                  onSubmit(action)
                }
              }}
            >
              {isMap ? `${label(action)} (Karte)` : label(action)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
