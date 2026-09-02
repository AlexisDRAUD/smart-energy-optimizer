BEGIN;

INSERT INTO users (email, password_hash, role, is_active, created_at)
VALUES
    (
        'camille.martin@enervision.demo',
        '$argon2id$v=19$m=65536,t=3,p=4$XOnH4+suCV9Wi7LUyKbxvg$DUZL7V5oV1Ioy6JMcQxrEqhtNm3a4ddAxF1CxMiKFGk',
        'admin',
        true,
        now()
    ),
    (
        'lucas.bernard@enervision.demo',
        '$argon2id$v=19$m=65536,t=3,p=4$XOnH4+suCV9Wi7LUyKbxvg$DUZL7V5oV1Ioy6JMcQxrEqhtNm3a4ddAxF1CxMiKFGk',
        'operator',
        true,
        now()
    ),
    (
        'marc.legrand@enervision.demo',
        '$argon2id$v=19$m=65536,t=3,p=4$XOnH4+suCV9Wi7LUyKbxvg$DUZL7V5oV1Ioy6JMcQxrEqhtNm3a4ddAxF1CxMiKFGk',
        'viewer',
        true,
        now()
    )
ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    is_active = EXCLUDED.is_active;

INSERT INTO sites (
    site_id, site_type, site_name, location, capacity_kw, status, first_seen_at, last_seen_at
)
VALUES
    ('LYO-01', 'office', 'Atelier Lyon Gerland', 'Lyon, France', 850, 'active', now(), now()),
    ('GRE-01', 'factory', 'Usine Grenoble Sud', 'Grenoble, France', 1200, 'active', now(), now()),
    ('NAN-01', 'warehouse', 'Entrepot Nantes Est', 'Nantes, France', 500, 'active', now(), now())
ON CONFLICT (site_id) DO UPDATE SET
    site_type = EXCLUDED.site_type,
    site_name = EXCLUDED.site_name,
    location = EXCLUDED.location,
    capacity_kw = EXCLUDED.capacity_kw,
    status = EXCLUDED.status,
    last_seen_at = EXCLUDED.last_seen_at;

DELETE FROM readings WHERE site_id IN ('LYO-01', 'GRE-01', 'NAN-01');

WITH mock_sites (site_id, base_consumption) AS (
    VALUES
        ('LYO-01', 278.0::double precision),
        ('GRE-01', 436.0::double precision),
        ('NAN-01', 164.0::double precision)
),
mock_points AS (
    SELECT
        mock_sites.site_id,
        mock_sites.base_consumption,
        minute_offset,
        date_trunc('minute', now()) - (1439 - minute_offset) * interval '1 minute' AS measured_at,
        minute_offset IN (180, 720, 1260) AS is_imputed
    FROM mock_sites
    CROSS JOIN generate_series(0, 1439) AS series(minute_offset)
)
INSERT INTO readings (
    site_id,
    measured_at,
    consumption_kwh,
    consumption_kwh_raw,
    is_imputed,
    imputation_method,
    temperature_celsius,
    humidity_percent,
    data_quality,
    null_reasons,
    ingested_at
)
SELECT
    site_id,
    measured_at,
    base_consumption * (0.75 + (minute_offset % 10) * 0.01),
    CASE
        WHEN is_imputed THEN NULL
        ELSE base_consumption * (0.75 + (minute_offset % 10) * 0.01)
    END,
    is_imputed,
    CASE WHEN is_imputed THEN 'report' ELSE NULL END,
    20 + (minute_offset % 5),
    45 + (minute_offset % 10),
    CASE WHEN is_imputed THEN 'partial' ELSE 'good' END,
    CASE
        WHEN is_imputed THEN ARRAY['scheduled_sensor_maintenance']::text[]
        ELSE ARRAY[]::text[]
    END,
    now()
FROM mock_points
ON CONFLICT (site_id, measured_at) DO UPDATE SET
    consumption_kwh = EXCLUDED.consumption_kwh,
    consumption_kwh_raw = EXCLUDED.consumption_kwh_raw,
    is_imputed = EXCLUDED.is_imputed,
    imputation_method = EXCLUDED.imputation_method,
    temperature_celsius = EXCLUDED.temperature_celsius,
    humidity_percent = EXCLUDED.humidity_percent,
    data_quality = EXCLUDED.data_quality,
    null_reasons = EXCLUDED.null_reasons,
    ingested_at = EXCLUDED.ingested_at;

DELETE FROM sensor_status WHERE site_id IN ('LYO-01', 'GRE-01', 'NAN-01');
INSERT INTO sensor_status (site_id, sensor, observed_at, status, failing_until)
SELECT
    site_id,
    sensor,
    now(),
    'ok',
    NULL
FROM (VALUES ('LYO-01'), ('GRE-01'), ('NAN-01')) AS mock_sites(site_id)
CROSS JOIN (
    VALUES ('consumption'), ('electrical'), ('temperature'), ('humidity'), ('network')
) AS mock_sensors(sensor);

INSERT INTO data_quality_daily (
    site_id, day, expected_points, received_points, missing_points, null_points, imputed_points, computed_at
)
SELECT site_id, current_date, 1440, 1440, 0, 3, 3, now()
FROM (VALUES ('LYO-01'), ('GRE-01'), ('NAN-01')) AS mock_sites(site_id)
ON CONFLICT (site_id, day) DO UPDATE SET
    expected_points = EXCLUDED.expected_points,
    received_points = EXCLUDED.received_points,
    missing_points = EXCLUDED.missing_points,
    null_points = EXCLUDED.null_points,
    imputed_points = EXCLUDED.imputed_points,
    computed_at = EXCLUDED.computed_at;

DELETE FROM predictions WHERE model_name = 'mock-moving-average';
INSERT INTO predictions (
    site_id, predicted_at, target_at, horizon_minutes, model_name, model_version, predicted_kwh, actual_kwh, scored_at
)
SELECT
    site_id,
    now(),
    now() + interval '2 hours',
    120,
    'mock-moving-average',
    'mock-1',
    predicted_kwh,
    NULL,
    NULL
FROM (
    VALUES
        ('LYO-01', 282.0::double precision),
        ('GRE-01', 443.0::double precision),
        ('NAN-01', 168.0::double precision)
) AS mock_predictions(site_id, predicted_kwh);

DELETE FROM alerts WHERE message = 'Mock: consommation elevee detectee sur Grenoble Sud.';
INSERT INTO alerts (
    site_id, detected_at, type, severity, message, value, threshold_value, status, acknowledged_at, acknowledged_by
)
VALUES (
    'GRE-01',
    now(),
    'threshold',
    'high',
    'Mock: consommation elevee detectee sur Grenoble Sud.',
    1130,
    1080,
    'open',
    NULL,
    NULL
);

DELETE FROM etl_runs WHERE error_message = 'mock seed';
INSERT INTO etl_runs (
    started_at, finished_at, window_start, window_end, rows_read, rows_written, rows_imputed, status, error_message
)
VALUES (
    now() - interval '1 minute',
    now(),
    now() - interval '30 minutes',
    now(),
    4320,
    4320,
    9,
    'ok',
    'mock seed'
);

COMMIT;

SELECT 'mock data loaded' AS result;
