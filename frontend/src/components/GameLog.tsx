// Scrollable history of applied actions (from GET /games/{id}/log).
import React from 'react'

import { useGameLog } from '../hooks/useGameLog'

interface GameLogProps {
  gameId: number | null
  sequence: number
}

export function GameLog({ gameId, sequence }: GameLogProps): React.ReactElement {
  const { events, isLoading } = useGameLog(gameId, sequence)

  return (
    <div className="game-log" data-testid="game-log">
      <h2>Verlauf</h2>
      {isLoading && <p>Lädt…</p>}
      <ol className="game-log__list">
        {events.map((event) => (
          <li key={event.sequence} data-testid={`log-${event.sequence}`}>
            <span className="log-seq">#{event.sequence}</span>
            <span className="log-type">{event.type}</span>
            {event.player_id && <span className="log-player">{event.player_id}</span>}
          </li>
        ))}
      </ol>
    </div>
  )
}
