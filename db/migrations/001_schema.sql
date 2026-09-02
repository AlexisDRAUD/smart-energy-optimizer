-- Schema initial. Reprend docs/data-contract.md, qui fait foi.
-- Joue par l'image postgres a la creation du volume, dans l'ordre alphabetique
-- des fichiers de ce dossier. Voir README.md a cote.
--
-- Les tables sont dans l'ordre du flux : brut ecrit par le collecteur, transforme
-- ecrit par l'ETL, tables de service ecrites par l'API. Le modele n'ecrit rien.

BEGIN;

-- ---------------------------------------------------------------------------
-- Couche brute. Ecrite par services/collector. Insertion seulement.
-- ---------------------------------------------------------------------------

-- Les mesures. Volumineuse, partitionnee par mois sur l'horodatage de reception.
CREATE TABLE raw_readings (
    id          bigserial,
    received_at timestamptz NOT NULL DEFAULT now(),
    source      text        NOT NULL,
    payload     jsonb       NOT NULL,
    CONSTRAINT raw_readings_pkey PRIMARY KEY (id, received_at),
    CONSTRAINT raw_readings_source_check
        CHECK (source IN ('api_current', 'api_backfill', 'csv_import'))
) PARTITION BY RANGE (received_at);

CREATE TABLE raw_readings_2026_09 PARTITION OF raw_readings
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE raw_readings_2026_10 PARTITION OF raw_readings
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE raw_readings_2026_11 PARTITION OF raw_readings
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE raw_readings_2026_12 PARTITION OF raw_readings
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

-- Filet de securite : une insertion hors des bornes ci-dessus atterrit ici
-- au lieu d'echouer. L'amorcage ecrit des donnees de 2023 et 2024, il passe par la.
CREATE TABLE raw_readings_default PARTITION OF raw_readings DEFAULT;

CREATE INDEX raw_readings_source_idx ON raw_readings (source, received_at);

-- Le referentiel et l'etat des capteurs. Petite, relue souvent, non partitionnee.
-- Separee des mesures : ces lignes n'ont ni le meme volume ni la meme duree de vie.
CREATE TABLE raw_snapshots (
    id          bigserial   PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    source      text        NOT NULL,
    payload     jsonb       NOT NULL,
    CONSTRAINT raw_snapshots_source_check
        CHECK (source IN ('api_sites', 'api_sensors'))
);

CREATE INDEX raw_snapshots_source_idx ON raw_snapshots (source, received_at DESC);

-- ---------------------------------------------------------------------------
-- Couche transformee. Ecrite par services/etl.
-- ---------------------------------------------------------------------------

-- Referentiel des sites. Les libelles ne sont pas repetes sur chaque mesure.
CREATE TABLE sites (
    site_id       text PRIMARY KEY,
    site_type     text,
    site_name     text,
    location      text,
    capacity_kw   double precision,
    status        text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now()
);

-- Les mesures controlees, reparees, typees.
CREATE TABLE readings (
    site_id             text        NOT NULL,
    measured_at         timestamptz NOT NULL,
    consumption_kwh     double precision,
    consumption_kwh_raw double precision,
    is_imputed          boolean     NOT NULL DEFAULT false,
    imputation_method   text,
    temperature_celsius double precision,
    humidity_percent    double precision,
    data_quality        text,
    null_reasons        text[]      NOT NULL DEFAULT '{}',
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    -- Cle unique. C'est elle qui rend le job de transformation rejouable
    -- sans creer de doublon.
    CONSTRAINT readings_pkey PRIMARY KEY (site_id, measured_at),
    CONSTRAINT readings_data_quality_check
        CHECK (data_quality IN ('good', 'partial', 'degraded', 'critical')
            OR data_quality IS NULL),
    CONSTRAINT readings_imputation_method_check
        CHECK (imputation_method IN ('interpolation', 'report') OR imputation_method IS NULL),
    CONSTRAINT readings_imputation_coherence
        CHECK ((is_imputed AND imputation_method IS NOT NULL)
            OR (NOT is_imputed AND imputation_method IS NULL))
);

COMMENT ON COLUMN readings.consumption_kwh_raw IS
    'Ce que la source a envoye. Seule base de calcul de l''imputation. Jamais reecrite.';
COMMENT ON COLUMN readings.consumption_kwh IS
    'Valeur utilisee, imputee ou non. Une valeur reelle n''est jamais ecrasee.';
COMMENT ON COLUMN readings.is_imputed IS
    'Porte sur consumption_kwh uniquement. La meteo n''est jamais imputee.';
COMMENT ON COLUMN readings.imputation_method IS
    'Porte sur consumption_kwh uniquement.';

-- Pas de cle etrangere de readings vers sites, volontairement. Un site inconnu
-- apparu dans la source ferait echouer le job de transformation, alors que la
-- regle du projet est que les controles de qualite marquent au lieu de bloquer.

CREATE INDEX readings_measured_at_idx ON readings (measured_at DESC);
CREATE INDEX readings_site_time_idx   ON readings (site_id, measured_at DESC);

-- Historique de sante des capteurs. Sans historisation, la page Qualite ne
-- montre que l'instant present, ce qui ne permet aucun diagnostic.
CREATE TABLE sensor_status (
    site_id       text        NOT NULL,
    sensor        text        NOT NULL,
    observed_at   timestamptz NOT NULL,
    status        text        NOT NULL,
    failing_until timestamptz,
    CONSTRAINT sensor_status_pkey PRIMARY KEY (site_id, sensor, observed_at),
    CONSTRAINT sensor_status_sensor_check
        CHECK (sensor IN ('consumption', 'electrical', 'temperature', 'humidity', 'network')),
    CONSTRAINT sensor_status_status_check
        CHECK (status IN ('ok', 'failing'))
);

CREATE INDEX sensor_status_site_time_idx ON sensor_status (site_id, observed_at DESC);

-- Trace des passes de l'ETL. Source du bandeau "derniere synchro" du dashboard.
-- Sans elle, personne ne sait si l'absence de donnees vient d'un trou de collecte
-- ou d'un ETL arrete.
CREATE TABLE etl_runs (
    id            bigserial   PRIMARY KEY,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    window_start  timestamptz,
    window_end    timestamptz,
    rows_read     integer     NOT NULL DEFAULT 0,
    rows_written  integer     NOT NULL DEFAULT 0,
    rows_imputed  integer     NOT NULL DEFAULT 0,
    status        text        NOT NULL DEFAULT 'running',
    error_message text,
    CONSTRAINT etl_runs_status_check
        CHECK (status IN ('running', 'ok', 'partial', 'failed'))
);

CREATE INDEX etl_runs_started_idx ON etl_runs (started_at DESC);

-- Resume par site et par jour, ecrit a la fin de chaque passe pour les jours
-- touches. Le dashboard le lit directement au lieu de rescanner readings.
CREATE TABLE data_quality_daily (
    site_id         text    NOT NULL,
    day             date    NOT NULL,
    expected_points integer NOT NULL DEFAULT 0,
    received_points integer NOT NULL DEFAULT 0,
    missing_points  integer NOT NULL DEFAULT 0,
    null_points     integer NOT NULL DEFAULT 0,
    imputed_points  integer NOT NULL DEFAULT 0,
    computed_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT data_quality_daily_pkey PRIMARY KEY (site_id, day)
);

CREATE INDEX data_quality_daily_day_idx ON data_quality_daily (day DESC);

-- ---------------------------------------------------------------------------
-- Tables de service. Ecrites par services/api.
-- services/ml n'ecrit rien en base, il publie un artefact dans MLflow.
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id            bigserial   PRIMARY KEY,
    email         text        NOT NULL UNIQUE,
    password_hash text        NOT NULL,
    role          text        NOT NULL DEFAULT 'viewer',
    is_active     boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_role_check CHECK (role IN ('viewer', 'operator', 'admin'))
);

-- Chaque prediction emise est conservee. actual_kwh est rempli plus tard par
-- l'ETL, quand la mesure reelle arrive, soit deux heures apres l'emission :
-- une prediction non conservee ne se compare a rien.
CREATE TABLE predictions (
    id              bigserial   PRIMARY KEY,
    site_id         text        NOT NULL,
    predicted_at    timestamptz NOT NULL DEFAULT now(),
    target_at       timestamptz NOT NULL,
    horizon_minutes integer     NOT NULL DEFAULT 120,  -- deux heures
    model_name      text        NOT NULL,
    model_version   text        NOT NULL,
    predicted_kwh   double precision NOT NULL,
    actual_kwh      double precision,
    -- Calcule par la base. Deux services qui calculent le meme ecart finissent
    -- par ne pas l'ecrire pareil.
    absolute_error  double precision
        GENERATED ALWAYS AS (abs(predicted_kwh - actual_kwh)) STORED,
    scored_at       timestamptz,
    -- Un redemarrage de l'API ne doit pas creer une seconde prediction pour le
    -- meme instant.
    CONSTRAINT predictions_unique
        UNIQUE (site_id, target_at, model_version, horizon_minutes)
);

CREATE INDEX predictions_site_target_idx ON predictions (site_id, target_at DESC);
CREATE INDEX predictions_pending_idx     ON predictions (target_at) WHERE actual_kwh IS NULL;

-- Alertes emises par notre API. Celles de la source arrivent dans le brut et
-- servent de reference de comparaison, elles ne sont pas recopiees ici.
CREATE TABLE alerts (
    id              bigserial   PRIMARY KEY,
    site_id         text        NOT NULL,
    detected_at     timestamptz NOT NULL,
    type            text        NOT NULL,
    severity        text        NOT NULL,
    message         text        NOT NULL,
    value           double precision,
    threshold_value double precision,
    status          text        NOT NULL DEFAULT 'open',
    acknowledged_at timestamptz,
    acknowledged_by bigint      REFERENCES users (id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT alerts_type_check
        CHECK (type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor')),
    CONSTRAINT alerts_severity_check
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT alerts_status_check
        CHECK (status IN ('open', 'acknowledged', 'closed')),
    CONSTRAINT alerts_ack_coherence
        CHECK ((status = 'open' AND acknowledged_at IS NULL)
            OR (status <> 'open')),
    -- Le meme depassement releve deux fois ne cree pas deux alertes.
    CONSTRAINT alerts_unique UNIQUE (site_id, type, detected_at)
);

CREATE INDEX alerts_open_idx ON alerts (detected_at DESC) WHERE status = 'open';
CREATE INDEX alerts_site_idx ON alerts (site_id, detected_at DESC);

COMMIT;
