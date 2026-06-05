// Modal shown when the server rejects a move. Explains why it was not possible
// and lists the moves that *are* currently allowed, so the player is never left
// staring at a raw error. Display only — it reads the store's legal actions.
import React from 'react'

import type { LegalActionsResponse } from '../api/types'
import { actionLabel } from '../help'

interface ActionErrorModalProps {
  message: string
  legalActions: LegalActionsResponse | null
  onClose: () => void
}

// Server messages are prefixed with a rule reference, e.g. "[5.5.4] No 2-Lok
// left". Split it into a badge + clean text.
function parseMessage(message: string): { rule: string | null; text: string } {
  const match = message.match(/^\[([^\]]+)\]\s*(.*)$/)
  if (match) return { rule: match[1], text: match[2] }
  return { rule: null, text: message }
}

export function ActionErrorModal({
  message,
  legalActions,
  onClose,
}: ActionErrorModalProps): React.ReactElement {
  const { rule, text } = parseMessage(message)
  const options = legalActions?.actions ?? []

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="action-error-title"
        data-testid="action-error-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="action-error-title" className="modal__title">
          ⚠️ Zug nicht möglich
        </h2>

        <p className="modal__message">
          {rule && <span className="modal__rule">Regel {rule}</span>}
          {text}
        </p>

        {options.length > 0 && (
          <div className="modal__options">
            <span className="modal__options-label">Stattdessen möglich:</span>
            <ul>
              {options.map((action, i) => (
                <li key={`${action.type}-${i}`}>{actionLabel(action)}</li>
              ))}
            </ul>
          </div>
        )}

        <button type="button" className="modal__close" onClick={onClose} autoFocus>
          Verstanden
        </button>
      </div>
    </div>
  )
}
