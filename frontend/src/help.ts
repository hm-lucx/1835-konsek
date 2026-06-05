// Player-facing guidance (German). Pure display data — no game logic. Maps the
// server's action types and phases onto friendly labels, tooltips, and
// "what should I do now?" explanations so the complex 1835 flow is navigable.
import type { Action, GameView, LegalActionsResponse } from './api/types'

interface ActionHelp {
  label: string
  hint: string
}

// Friendly label + tooltip per action type (keys are the server's snake_case
// `type` strings from view.legal_actions).
export const ACTION_HELP: Record<string, ActionHelp> = {
  buy_start_item: {
    label: 'Startpaket kaufen',
    hint: 'Kaufe dieses Objekt (Privatbahn oder Aktie) aus dem Startpaket.',
  },
  pass: {
    label: 'Passen',
    hint: 'Diese Runde aussetzen. Passen alle Spieler nacheinander, endet die Phase.',
  },
  buy_share_from_bank: {
    label: 'Aktie kaufen (Bank)',
    hint: 'Kaufe eine 10 %-Aktie direkt von der Bank zum aktuellen Kurs.',
  },
  buy_share_from_pool: {
    label: 'Aktie kaufen (Pool)',
    hint: 'Kaufe eine 10 %-Aktie aus dem offenen Pool zum aktuellen Kurs.',
  },
  sell_shares: {
    label: 'Aktie verkaufen',
    hint: 'Verkaufe eine 10 %-Aktie in den Pool. Der Kurs der Gesellschaft sinkt.',
  },
  lay_tile: {
    label: 'Gleis legen',
    hint: 'Neues Gleisplättchen legen: erst rechts ein Plättchen wählen, dann ein Feld auf der Karte anklicken.',
  },
  upgrade_tile: {
    label: 'Gleis ausbauen',
    hint: 'Ein bestehendes Plättchen durch eine höherwertige Variante ersetzen, dann Feld anklicken.',
  },
  place_station: {
    label: 'Bahnhof setzen',
    hint: 'Setze einen Bahnhofsmarker. Aktion wählen, dann ein Feld auf der Karte anklicken.',
  },
  choose_baden_home_station: {
    label: 'Baden-Heimatbahnhof',
    hint: 'Lege den Heimatbahnhof der Badischen Bahn fest, dann Feld anklicken.',
  },
  use_ob_ability: {
    label: 'OB-Fähigkeit nutzen',
    hint: 'Sonderfähigkeit der Privatbahn Ostbahn einsetzen.',
  },
  use_nf_ability: {
    label: 'NF-Fähigkeit nutzen',
    hint: 'Sonderfähigkeit der Privatbahn Nürnberg-Fürth einsetzen.',
  },
  use_pf_build_ability: {
    label: 'PF-Bau nutzen',
    hint: 'Bau-Sonderfähigkeit der Pfalzbahn einsetzen.',
  },
  use_pf_station_ability: {
    label: 'PF-Bahnhof nutzen',
    hint: 'Bahnhof-Sonderfähigkeit der Pfalzbahn einsetzen.',
  },
  run_trains: {
    label: 'Züge fahren',
    hint: 'Ermittle die Einnahmen der Züge dieser Gesellschaft.',
  },
  declare_dividend: {
    label: 'Dividende ausschütten',
    hint: 'Einnahmen an die Aktionäre auszahlen. Der Aktienkurs steigt in der Regel.',
  },
  withhold_dividend: {
    label: 'Einbehalten',
    hint: 'Einnahmen in der Firmenkasse behalten. Der Aktienkurs sinkt.',
  },
  buy_train_from_bank: {
    label: 'Zug kaufen (Bank)',
    hint: 'Kaufe die nächste verfügbare Lok von der Bank.',
  },
  buy_train_from_company: {
    label: 'Zug kaufen (Gesellschaft)',
    hint: 'Kaufe eine Lok von einer anderen Gesellschaft.',
  },
  buy_mandatory_train: {
    label: 'Pflichtzug kaufen',
    hint: 'Diese Gesellschaft hat keinen Zug und muss einen kaufen.',
  },
}

// Map actions need a second step (click a hex), so they get the "(Karte)" suffix.
export const MAP_ACTION_TYPES = new Set([
  'lay_tile',
  'upgrade_tile',
  'place_station',
  'choose_baden_home_station',
])

// Append the action's inline params (e.g. the bought item id) to the label so
// repeated buttons stay distinguishable.
function actionParams(action: Action): string {
  return Object.entries(action)
    .filter(([key]) => key !== 'type')
    .map(([, value]) => String(value))
    .join(' ')
}

export function actionLabel(action: Action): string {
  const base = ACTION_HELP[action.type]?.label ?? action.type
  const params = actionParams(action)
  return params ? `${base} · ${params}` : base
}

export function actionHint(action: Action): string {
  return ACTION_HELP[action.type]?.hint ?? action.type
}

interface PhaseGuide {
  title: string
  body: string
}

// "Was ist jetzt zu tun?" per phase / OR sub-phase.
const PHASE_GUIDES: Record<string, PhaseGuide> = {
  start_packet_ar: {
    title: 'Startpaket-Phase',
    body: 'Kaufe reihum ein Objekt aus dem Startpaket (Privatbahn oder Aktie) – oder passe. Die Phase endet, wenn alle nacheinander passen.',
  },
  ar: {
    title: 'Aktienrunde',
    body: 'Kaufe Aktien von Bank oder Pool, verkaufe eigene Aktien – oder passe. Wer die Mehrheit hält, wird Direktor und leitet die Gesellschaft.',
  },
  'or:build': {
    title: 'Operationsrunde · Bauphase',
    body: 'Lege oder erweitere ein Gleisplättchen: Aktion wählen, rechts ein Plättchen markieren, dann ein Feld auf der Karte anklicken. Oder passe.',
  },
  'or:station': {
    title: 'Operationsrunde · Bahnhof',
    body: 'Setze einen Bahnhof: „Bahnhof setzen“ wählen und ein Feld auf der Karte anklicken. Oder passe.',
  },
  'or:run': {
    title: 'Operationsrunde · Fahren',
    body: 'Lasse die Züge der Gesellschaft fahren, um die Einnahmen zu ermitteln.',
  },
  'or:dividend_decision': {
    title: 'Operationsrunde · Dividende',
    body: 'Schütte die Einnahmen als Dividende aus (Kurs steigt) oder behalte sie in der Kasse (Kurs sinkt).',
  },
  'or:buy_train': {
    title: 'Operationsrunde · Zugkauf',
    body: 'Kaufe Loks von der Bank oder anderen Gesellschaften. Ohne Zug ist mindestens ein Kauf Pflicht. Oder passe.',
  },
  'or:done': {
    title: 'Operationsrunde abgeschlossen',
    body: 'Diese Gesellschaft ist fertig. Der nächste Spielabschnitt beginnt automatisch.',
  },
}

export function phaseGuide(view: GameView): PhaseGuide {
  if (view.game_over) {
    return { title: 'Spiel beendet', body: 'Die Partie ist vorbei. Vergleiche Vermögen und Aktienwerte der Spieler.' }
  }
  if (view.phase === 'or' && view.or_phase) {
    return PHASE_GUIDES[`or:${view.or_phase}`] ?? { title: 'Operationsrunde', body: '' }
  }
  return PHASE_GUIDES[view.phase] ?? { title: view.phase, body: '' }
}

// A light, safe "next step" cue: the single actionable choice if there is only
// one besides passing, else null. Avoids giving strategic advice.
export function suggestedAction(legalActions: LegalActionsResponse | null): Action | null {
  const actionable = (legalActions?.actions ?? []).filter((a) => a.type !== 'pass')
  return actionable.length === 1 ? actionable[0] : null
}
