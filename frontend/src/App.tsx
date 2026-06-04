import React, { useState } from 'react'

import { createGame } from './api/client'
import type { Action } from './api/types'
import { ActionBar } from './components/ActionBar'
import { CompanyPanel } from './components/CompanyPanel'
import { GameLog } from './components/GameLog'
import { HexMap } from './components/HexMap'
import { PlayerPanel } from './components/PlayerPanel'
import { StockMarket } from './components/StockMarket'
import { TileTray } from './components/TileTray'
import { TrainPool } from './components/TrainPool'
import { useGameStore } from './store/gameStore'
import './App.css'

function App(): React.ReactElement {
  const { gameId, playerId, view, legalActions, error, connect, submit } = useGameStore()
  const [armedMapAction, setArmedMapAction] = useState<string | null>(null)
  const [selectedTileId, setSelectedTileId] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)

  async function startSoloGame(): Promise<void> {
    setStarting(true)
    try {
      const id = await createGame(3, 'solo@example.com')
      await connect(id, 'Player 1')
    } finally {
      setStarting(false)
    }
  }

  function handleSubmit(action: Action): void {
    setArmedMapAction(null)
    void submit(action)
  }

  function handleHexClick(q: number, r: number): void {
    if (!armedMapAction) return
    const action: Action = { type: armedMapAction, q, r }
    if (armedMapAction === 'lay_tile' || armedMapAction === 'upgrade_tile') {
      action.tile_id = selectedTileId ?? 0
    }
    handleSubmit(action)
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>1835 Konsek</h1>
        {gameId === null ? (
          <button type="button" onClick={() => void startSoloGame()} disabled={starting}>
            {starting ? 'Starte…' : 'Neues Solo-Spiel'}
          </button>
        ) : (
          <span className="app__game-id">
            Spiel #{gameId} · Zug {view?.sequence ?? 0}
            {view?.game_over ? ' · beendet' : ''}
          </span>
        )}
      </header>

      {error && (
        <div className="app__error" role="alert">
          {error}
        </div>
      )}

      {view ? (
        <main className="app__layout">
          <section className="app__map">
            <HexMap
              view={view}
              armedMapAction={armedMapAction}
              selectedTileId={selectedTileId}
              onHexClick={handleHexClick}
            />
            <StockMarket stocks={view.stocks} />
          </section>

          <aside className="app__side">
            <PlayerPanel players={view.players} activePlayerId={playerId} />
            <CompanyPanel companies={view.companies} />
            <TileTray
              tiles={view.tiles}
              coloredPhase={view.colored_phase}
              selectedTileId={selectedTileId}
              onSelectTile={setSelectedTileId}
            />
            <TrainPool trainPrices={view.train_prices} availableTrains={view.available_trains} />
            <GameLog gameId={gameId} sequence={view.sequence} />
          </aside>

          <footer className="app__footer">
            <ActionBar
              legalActions={legalActions}
              armedMapAction={armedMapAction}
              onSubmit={handleSubmit}
              onArmMapAction={setArmedMapAction}
            />
          </footer>
        </main>
      ) : (
        <p className="app__hint">Starte ein Spiel, um das Brett zu sehen.</p>
      )}
    </div>
  )
}

export default App
