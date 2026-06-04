import React from 'react'

import type { PlayerState } from '../api/types'

interface PlayerPanelProps {
  players: PlayerState[]
  activePlayerId: string
}

export function PlayerPanel({ players, activePlayerId }: PlayerPanelProps): React.ReactElement {
  return (
    <div className="player-panel" data-testid="player-panel">
      <h2>Spieler</h2>
      {players.map((player) => (
        <div
          key={player.player_id}
          className={`player-card${player.player_id === activePlayerId ? ' player-card--active' : ''}`}
          data-testid={`player-${player.player_id}`}
        >
          <div className="player-card__head">
            <strong>{player.player_id}</strong>
            <span className="player-cash">{player.cash} M</span>
          </div>
          <div className="player-card__meta">
            Papiere: {player.paper_count}/{player.paper_limit}
            {player.bankrupt ? ' · bankrott' : ''}
          </div>
          <div className="player-shares">
            {Object.entries(player.shares)
              .filter(([, pct]) => pct > 0)
              .map(([companyId, pct]) => (
                <span key={companyId} className="share-chip">
                  {companyId} {pct}%
                </span>
              ))}
          </div>
          {player.privates.length > 0 && (
            <div className="player-privates">Privatbahnen: {player.privates.join(', ')}</div>
          )}
        </div>
      ))}
    </div>
  )
}
