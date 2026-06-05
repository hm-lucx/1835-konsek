// "Was ist jetzt zu tun?" guidance banner. Explains the current phase and who
// is on turn, and nudges through the two-step map actions. Display only.
import React from 'react'

import type { GameView } from '../api/types'
import { phaseGuide } from '../help'

interface PhaseGuideProps {
  view: GameView
  armedMapAction: string | null
  selectedTileId: number | null
}

export function PhaseGuide({
  view,
  armedMapAction,
  selectedTileId,
}: PhaseGuideProps): React.ReactElement {
  const guide = phaseGuide(view)

  // While a map action is armed, the player's immediate next step is to click a
  // hex — surface that prominently, including the missing tile selection.
  let armedHint: string | null = null
  if (armedMapAction) {
    const needsTile = armedMapAction === 'lay_tile' || armedMapAction === 'upgrade_tile'
    armedHint =
      needsTile && !selectedTileId
        ? 'Wähle zuerst rechts ein Gleisplättchen, dann klicke ein Feld auf der Karte.'
        : 'Klicke jetzt ein Feld auf der Karte, um die Aktion auszuführen.'
  }

  return (
    <div className="phase-guide" data-testid="phase-guide">
      <div className="phase-guide__main">
        <span className="phase-guide__badge">Nächster Schritt</span>
        <strong className="phase-guide__title">{guide.title}</strong>
        {view.current_actor && !view.game_over && (
          <span className="phase-guide__actor">am Zug: {view.current_actor}</span>
        )}
      </div>
      <p className="phase-guide__body">{armedHint ?? guide.body}</p>
    </div>
  )
}
