SET ROLE haf_stats_owner;

CREATE OR REPLACE FUNCTION haf_stats_endpoints.ws_witness_reward_stats(
  "producer" TEXT,
  "start_date" TIMESTAMP = NULL,
  "end_date" TIMESTAMP = NULL
)
RETURNS jsonb AS $function$
DECLARE
  _producer_id INT;
  _start DATE := COALESCE("start_date", '2016-03-23'::TIMESTAMP)::DATE;
  _end DATE := COALESCE("end_date", NOW()::TIMESTAMP)::DATE;
BEGIN
  -- IF (SELECT hive.is_app_in_sync('haf_stats') IS FALSE) THEN
  --   RAISE EXCEPTION 'haf_stats is not in sync';
  -- END IF;
  IF _start > _end THEN
    RAISE EXCEPTION 'start_date cannot be later than end_date';
  END IF;

  SELECT a.id INTO _producer_id FROM hafd.accounts a WHERE a.name = "producer";
  IF _producer_id IS NULL THEN
    RAISE EXCEPTION 'Account % does not exist', "producer";
  END IF;

  RETURN (
    SELECT jsonb_build_object(
      'total_vests', SUM(f.vests_nai),
      'total_hive', SUM(ROUND(f.vests_nai * COALESCE((r.first_rate + r.last_rate) / 2, 0), 0)),
      'total_blocks', SUM(f.op_count)
    )
    FROM haf_stats_backend.account_financial_daily f
    LEFT JOIN LATERAL (
      SELECT (SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
        FROM hafd.blocks b
        WHERE b.created_at >= f.day AND b.created_at < f.day + 1
        ORDER BY b.created_at ASC LIMIT 1) AS first_rate,
        (SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
        FROM hafd.blocks b
        WHERE b.created_at >= f.day AND b.created_at < f.day + 1
        ORDER BY b.created_at DESC LIMIT 1) AS last_rate
    ) r ON true
    WHERE f.account_id = _producer_id
      AND f.category = 'producer_reward_operation'
      AND f.direction = 'incoming'
      AND f.day >= _start AND f.day <= _end
  );
END $function$
LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION haf_stats_endpoints.ws_witness_reward_history(
  "producer" TEXT,
  "start_date" TIMESTAMP = NULL,
  "end_date" TIMESTAMP = NULL,
  "direction" TEXT = 'asc',
  "granularity" TEXT = 'daily'
)
RETURNS jsonb AS $function$
DECLARE
  _producer_id INT;
  _min_date DATE;
  _max_date DATE;
  _first_active DATE;
  _last_active DATE;
  _start DATE;
  _end DATE;
  _trunc TEXT;
  -- Locals required: an unqualified parameter named "direction" is ambiguous with
  -- account_financial_daily.direction inside PL/pgSQL (daily_stats has no such column).
  _direction TEXT := "direction";
  _granularity TEXT := "granularity";
BEGIN
  -- IF (SELECT hive.is_app_in_sync('haf_stats') IS FALSE) THEN
  --   RAISE EXCEPTION 'haf_stats is not in sync';
  -- END IF;
  IF _direction IS NULL OR _direction NOT IN ('asc', 'desc') THEN
    RAISE EXCEPTION 'invalid direction: %', COALESCE(_direction, '(null)');
  END IF;
  IF _granularity IS NULL OR _granularity NOT IN ('daily', 'monthly', 'yearly') THEN
    RAISE EXCEPTION 'invalid granularity: %', COALESCE(_granularity, '(null)');
  END IF;

  SELECT a.id INTO _producer_id FROM hafd.accounts a WHERE a.name = "producer";
  IF _producer_id IS NULL THEN
    RAISE EXCEPTION 'Account % does not exist', "producer";
  END IF;

  SELECT MIN(f.day), MAX(f.day) INTO _min_date, _max_date
  FROM haf_stats_backend.account_financial_daily f
  WHERE f.account_id = _producer_id
    AND f.category = 'producer_reward_operation'
    AND f.direction = 'incoming';

  _start := COALESCE("start_date"::date, _min_date);
  _end := COALESCE("end_date"::date, _max_date);

  IF _start > _end THEN
    RAISE EXCEPTION 'start_date cannot be later than end_date';
  END IF;

  -- Empty-edge trim: clamp the series to the first/last day with rewards inside
  -- the requested window. Interior gaps (empty days/periods between rewarded
  -- ones) are preserved.
  SELECT MIN(f.day), MAX(f.day) INTO _first_active, _last_active
  FROM haf_stats_backend.account_financial_daily f
  WHERE f.account_id = _producer_id
    AND f.category = 'producer_reward_operation'
    AND f.direction = 'incoming'
    AND f.day >= _start AND f.day <= _end;

  IF _first_active IS NULL THEN
    RETURN '[]'::jsonb;
  END IF;

  _start := _first_active;
  _end := _last_active;

  IF _granularity = 'daily' THEN
    RETURN (
      WITH daily AS (
        SELECT
          d.day,
          COALESCE(f.vests_nai, 0) AS vests,
          ROUND(COALESCE(f.vests_nai, 0)
            * COALESCE((r.first_rate + r.last_rate) / 2, 0), 0) AS hive,
          COALESCE(f.op_count, 0) AS blocks
        FROM (
          SELECT gs::date AS day
          FROM generate_series(_start::timestamp, _end::timestamp, '1 day'::interval) gs
        ) d
        LEFT JOIN haf_stats_backend.account_financial_daily f
          ON f.account_id = _producer_id
          AND f.day = d.day
          AND f.category = 'producer_reward_operation'
          AND f.direction = 'incoming'
        LEFT JOIN LATERAL (
          SELECT (SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
            FROM hafd.blocks b
            WHERE b.created_at >= d.day AND b.created_at < d.day + 1
            ORDER BY b.created_at ASC LIMIT 1) AS first_rate,
            (
              SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
              FROM hafd.blocks b
              WHERE b.created_at >= d.day AND b.created_at < d.day + 1
              ORDER BY b.created_at DESC LIMIT 1
            ) AS last_rate
        ) r ON true
        ORDER BY
          CASE WHEN _direction = 'desc' THEN d.day END DESC,
          CASE WHEN _direction = 'asc' THEN d.day END ASC
      )
      SELECT jsonb_agg(jsonb_build_object(
        'date', day::date, 'vests', vests, 'hive', hive, 'count', blocks
      )) FROM daily
    );
  ELSE
      _trunc := CASE _granularity WHEN 'monthly' THEN 'month' ELSE 'year' END;
      RETURN (
        WITH daily AS (
            SELECT
              d.day,
              COALESCE(f.vests_nai, 0) AS vests,
              ROUND(COALESCE(f.vests_nai, 0)
                    * COALESCE((r.first_rate + r.last_rate) / 2, 0), 0) AS hive,
              COALESCE(f.op_count, 0) AS blocks
            FROM (
              SELECT gs::date AS day
              FROM generate_series(_start::timestamp, _end::timestamp, '1 day'::interval) gs
            ) d
            LEFT JOIN haf_stats_backend.account_financial_daily f
              ON f.account_id = _producer_id
              AND f.day = d.day
              AND f.category = 'producer_reward_operation'
              AND f.direction = 'incoming'
            LEFT JOIN LATERAL (
              SELECT (SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
                FROM hafd.blocks b
                WHERE b.created_at >= d.day AND b.created_at < d.day + 1
                ORDER BY b.created_at ASC LIMIT 1) AS first_rate,
                (
                  SELECT b.total_vesting_fund_hive::numeric / b.total_vesting_shares
                  FROM hafd.blocks b
                  WHERE b.created_at >= d.day AND b.created_at < d.day + 1
                  ORDER BY b.created_at DESC LIMIT 1
                ) AS last_rate
            ) r ON true
        ),
        aggregated AS (
          SELECT DATE_TRUNC(_trunc, day) AS period,
            SUM(vests) AS vests,
            SUM(hive) AS hive,
            SUM(blocks) AS blocks
          FROM daily GROUP BY 1
        ),
        series AS (
          SELECT gs AS period
          FROM generate_series(
            DATE_TRUNC(_trunc, _start::timestamp),
            DATE_TRUNC(_trunc, _end::timestamp),
            CASE WHEN _granularity = 'monthly' THEN '1 month'::interval ELSE '1 year'::interval END
          ) gs
        ),
        history AS (
          SELECT s.period,
            COALESCE(a.vests, 0) AS vests,
            COALESCE(a.hive, 0) AS hive,
            COALESCE(a.blocks, 0) AS blocks
          FROM series s LEFT JOIN aggregated a ON a.period = s.period
          ORDER BY
            CASE WHEN _direction = 'desc' THEN s.period END DESC,
            CASE WHEN _direction = 'asc' THEN s.period END ASC
        )
        SELECT jsonb_agg(jsonb_build_object(
          'date', period::date, 'vests', vests, 'hive', hive, 'count', blocks
        )) FROM history
      );
  END IF;
END $function$
LANGUAGE plpgsql STABLE;

-- Curation stats
-- Grant these manually from haf_admin
/*
GRANT USAGE ON SCHEMA hivemind_app TO haf_stats_user;
GRANT SELECT ON hivemind_app.hive_votes TO haf_stats_user;
GRANT SELECT ON hivemind_app.hive_accounts TO haf_stats_user;
*/

CREATE OR REPLACE FUNCTION haf_stats_endpoints.hm_outgoing_votes_summary(voter VARCHAR, last_days INT, direction INT)
RETURNS jsonb AS $function$
BEGIN
  -- IF (SELECT hive.is_app_in_sync('hivemind_app') IS FALSE) THEN
  --   RAISE EXCEPTION 'hivemind_app is not in sync';
  -- END IF;
  IF last_days < 1 OR last_days > 30 THEN
    RAISE EXCEPTION 'last_days must be between 1 and 30';
  ELSIF direction != 1 AND direction != 2 THEN
    RAISE EXCEPTION 'direction must be 1 (upvote) or 2 (downvote)';
  ELSIF voter IS NULL OR LENGTH(voter) = 0 THEN
    RAISE EXCEPTION 'invalid voter';
  END IF;
  RETURN (
    WITH summary AS (
      SELECT aa.name as author, SUM(vote_percent) as vote_weight_agg, COUNT(v.author_id) as vote_count
      FROM hivemind_app.hive_votes v
      JOIN hivemind_app.hive_accounts aa ON
        aa.id = v.author_id
      JOIN hivemind_app.hive_accounts va ON
        va.id = v.voter_id
      WHERE va.name = voter AND v.last_update > NOW()::TIMESTAMP - (last_days * interval '1 day') AND (SELECT CASE WHEN direction = 1 THEN vote_percent > 0 ELSE vote_percent < 0 END)
      GROUP BY aa.name
      ORDER BY vote_count DESC, vote_weight_agg DESC
    )
    SELECT jsonb_agg(jsonb_build_object(
      'author', s.author,
      'weights', s.vote_weight_agg,
      'count', s.vote_count
    ))
    FROM summary s
  );
END $function$
LANGUAGE plpgsql STABLE;