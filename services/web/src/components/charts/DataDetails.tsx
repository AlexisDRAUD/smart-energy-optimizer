import type { ApiChartCoverage, ApiChartSamplingStats, ApiConsumptionChart } from '../../types/api'
import { formatDateTime, formatPercent } from '../../utils/formatters'

function CoverageDetails({ label, coverage }: Readonly<{ label: string; coverage: ApiChartCoverage }>) {
    return (
        <section>
            <h3>{label}</h3>
            <dl>
                <dt>Couverture exploitable</dt><dd>{formatPercent(coverage.percent)}</dd>
                <dt>Minutes attendues</dt><dd>{coverage.expected_minutes}</dd>
                <dt>Minutes reçues</dt><dd>{coverage.received_minutes}</dd>
                <dt>Minutes exploitables</dt><dd>{coverage.valid_minutes}</dd>
                <dt>Minutes absentes</dt><dd>{coverage.missing_minutes}</dd>
                <dt>Valeurs nulles</dt><dd>{coverage.null_minutes}</dd>
                <dt>Première observation</dt><dd>{formatDateTime(coverage.first_at)}</dd>
                <dt>Dernière observation</dt><dd>{formatDateTime(coverage.last_at)}</dd>
            </dl>
        </section>
    )
}

function SamplingDetails({ label, stats }: Readonly<{ label: string; stats: ApiChartSamplingStats }>) {
    return (
        <div className="sampling-row">
            <span>{label}</span>
            <strong>{stats.output_points}/{stats.input_points}</strong>
            <small>{stats.applied ? 'réduction appliquée' : 'série native conservée'}</small>
        </div>
    )
}

export function DataDetails({ chart }: Readonly<{ chart: ApiConsumptionChart }>) {
    const interval = chart.measurement_interval_seconds === null
        ? 'Non défini par le contrat Data'
        : `${chart.measurement_interval_seconds} secondes`

    return (
        <details className="data-details">
            <summary>Détails des données</summary>
            <div className="data-details-grid">
                <section>
                    <h3>Fenêtres et contrat</h3>
                    <dl>
                        <dt>Site</dt><dd>{chart.site_id}</dd>
                        <dt>Historique demandé</dt><dd>{formatDateTime(chart.start)} → {formatDateTime(chart.end)}</dd>
                        <dt>Futur demandé</dt><dd>{formatDateTime(chart.end)} → {formatDateTime(chart.future_end)}</dd>
                        <dt>Unité native</dt><dd>{chart.unit}</dd>
                        <dt>Base de l’unité</dt><dd>{chart.unit_basis} — aucune conversion</dd>
                        <dt>Cadence attendue</dt><dd>{chart.cadence_seconds} secondes</dd>
                        <dt>Durée physique d’une valeur</dt><dd>{interval}</dd>
                        <dt>Plafonds de lecture</dt><dd>{chart.max_readings} relevés · {chart.max_predictions} prédictions</dd>
                    </dl>
                </section>
                <section>
                    <h3>Prédiction sélectionnée</h3>
                    <dl>
                        <dt>Modèle</dt><dd>{chart.model_name}</dd>
                        <dt>Version</dt><dd>{chart.model_version}</dd>
                        <dt>Horizon</dt><dd>H+2 ({chart.horizon_minutes} minutes)</dd>
                    </dl>
                </section>
                <CoverageDetails label="Relevés réels" coverage={chart.reading_coverage} />
                <CoverageDetails label="Prédictions historiques" coverage={chart.prediction_coverage} />
                <CoverageDetails label="Prédictions futures" coverage={chart.future_coverage} />
                <section>
                    <h3>Affichage {chart.downsampling.algorithm.toUpperCase()}</h3>
                    <p>Cible : environ {chart.downsampling.target_points_per_series} points par série lorsque les ruptures le permettent.</p>
                    <SamplingDetails label="Réel" stats={chart.downsampling.readings} />
                    <SamplingDetails label="Prédit historique" stats={chart.downsampling.historical_predictions} />
                    <SamplingDetails label="Prédit futur" stats={chart.downsampling.future_predictions} />
                    <p className="data-details-note">Les couvertures et le dernier écart sont calculés sur les séries complètes. Les valeurs nulles et les bords des ruptures restent obligatoires.</p>
                </section>
            </div>
        </details>
    )
}
