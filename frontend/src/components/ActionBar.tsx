// Renders exactly the actions the server lists in legal_actions (no client-side
// rule logic). Board-targeted actions are "armed" so the player then clicks a
// hex on the map; all other actions submit immediately. Labels and tooltips
// come from the German help map; the single non-pass choice is highlighted.
import React from 'react'

import type { Action, LegalActionsResponse } from '../api/types'
import { actionHint, actionLabel, MAP_ACTION_TYPES, suggestedAction } from '../help'

interface ActionBarProps {
  legalActions: LegalActionsResponse | null
  armedMapAction: string | null
  onSubmit: (action: Action) => void
  onArmMapAction: (actionType: string | null) => void
}

export function ActionBar({
  legalActions,
  armedMapAction,
  onSubmit,
  onArmMapAction,
}: ActionBarProps): React.ReactElement {
  const actions = legalActions?.actions ?? []
  const suggested = suggestedAction(legalActions)

  return (
    <div className="action-bar" data-testid="action-bar">
      <div className="action-bar__phase">Wähle eine Aktion:</div>
      <div className="action-bar__buttons">
        {actions.length === 0 && <span className="action-bar__empty">Keine Aktionen</span>}
        {actions.map((action, index) => {
          const isMap = MAP_ACTION_TYPES.has(action.type)
          const armed = isMap && armedMapAction === action.type
          const isPass = action.type === 'pass'
          const isSuggested = suggested === action
          const classes = [
            'action-btn',
            isPass ? 'action-btn--ghost' : '',
            armed ? 'action-btn--armed' : '',
            isSuggested ? 'action-btn--suggested' : '',
          ]
            .filter(Boolean)
            .join(' ')
          return (
            <button
              key={`${action.type}-${index}`}
              type="button"
              className={classes}
              title={actionHint(action)}
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
              {isMap ? `${actionLabel(action)} ▸ Karte` : actionLabel(action)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
