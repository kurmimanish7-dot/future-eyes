from datetime import date, datetime, time, timedelta

import pandas as pd


class TimeMachineEngine:
    """
    Historical 10-minute market replay engine.

    Uses actual historical Angel One candle data.
    Paper-trading research only.
    Never places real orders.
    """

    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)

    def __init__(self, smart_api=None):
        self.smart_api = smart_api

    # =========================================================
    # EMPTY DATAFRAME
    # =========================================================

    @staticmethod
    def _empty():
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )

    # =========================================================
    # DATE NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_date(value):
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()

    # =========================================================
    # FETCH HISTORICAL DAY
    # =========================================================

    def fetch_day(
        self,
        exchange,
        token,
        selected_date,
    ):
        """
        Fetch actual historical 10-minute candles
        from Angel One.

        Returns:
            pandas.DataFrame
        """

        if self.smart_api is None:
            return self._empty()

        if not token:
            return self._empty()

        day = self._normalize_date(selected_date)

        # Saturday / Sunday
        if day.weekday() >= 5:
            return self._empty()

        from_datetime = datetime.combine(
            day,
            self.MARKET_OPEN,
        )

        to_datetime = datetime.combine(
            day,
            self.MARKET_CLOSE,
        )

        params = {
            "exchange": str(exchange),
            "symboltoken": str(token),
            "interval": "TEN_MINUTE",
            "fromdate": from_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "todate": to_datetime.strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        try:
            response = self.smart_api.getCandleData(
                params
            )
        except Exception:
            return self._empty()

        if not isinstance(response, dict):
            return self._empty()

        if not response.get("status"):
            return self._empty()

        rows = response.get("data")

        if not rows:
            return self._empty()

        try:
            df = pd.DataFrame(rows)
        except Exception:
            return self._empty()

        if df.empty:
            return self._empty()

        if len(df.columns) < 6:
            return self._empty()

        # Angel One candle format:
        # timestamp, open, high, low, close, volume

        df = df.iloc[:, :6].copy()

        df.columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        # =====================================================
        # DATA TYPES
        # =====================================================

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
            ]
        )

        if df.empty:
            return self._empty()

        df["volume"] = df["volume"].fillna(0)

        # =====================================================
        # CLEAN DATA
        # =====================================================

        df = df.drop_duplicates(
            subset=["timestamp"],
            keep="last",
        )

        df = df.sort_values(
            "timestamp"
        )

        # =====================================================
        # MARKET HOURS FILTER
        # =====================================================

        df = df[
            (df["timestamp"].dt.time >= self.MARKET_OPEN)
            & (
                df["timestamp"].dt.time
                < self.MARKET_CLOSE
            )
        ]

        return df.reset_index(drop=True)

    # =========================================================
    # BUILD 10-MINUTE REPLAY
    # =========================================================

    @staticmethod
    def build_replay(
        df,
        selected_date,
    ):
        """
        Converts historical candles into replay blocks.

        Each row represents one 10-minute market block.
        """

        if df is None or df.empty:
            return pd.DataFrame()

        day = TimeMachineEngine._normalize_date(
            selected_date
        )

        rows = []

        for _, candle in df.iterrows():

            timestamp = pd.Timestamp(
                candle["timestamp"]
            )

            start_datetime = timestamp.to_pydatetime()

            end_datetime = min(
                start_datetime
                + timedelta(minutes=10),
                datetime.combine(
                    day,
                    TimeMachineEngine.MARKET_CLOSE,
                ),
            )

            open_price = float(
                candle["open"]
            )

            high_price = float(
                candle["high"]
            )

            low_price = float(
                candle["low"]
            )

            close_price = float(
                candle["close"]
            )

            volume = float(
                candle.get(
                    "volume",
                    0,
                )
                or 0
            )

            # Previous block close
            if rows:
                previous_close = float(
                    rows[-1]["close"]
                )
            else:
                previous_close = open_price

            # =================================================
            # MOVEMENT CALCULATIONS
            # =================================================

            block_move = (
                close_price
                - open_price
            )

            net_points = (
                close_price
                - previous_close
            )

            range_points = (
                high_price
                - low_price
            )

            block_pct = (
                block_move
                / open_price
                * 100
                if open_price
                else 0.0
            )

            swing_pct = (
                net_points
                / previous_close
                * 100
                if previous_close
                else 0.0
            )

            range_pct = (
                range_points
                / open_price
                * 100
                if open_price
                else 0.0
            )

            # =================================================
            # DIRECTION
            # =================================================

            if block_move > 0:
                direction = "UP"

            elif block_move < 0:
                direction = "DOWN"

            else:
                direction = "FLAT"

            # =================================================
            # STORE BLOCK
            # =================================================

            rows.append(
                {
                    "date": day.isoformat(),

                    "start": start_datetime.strftime(
                        "%H:%M"
                    ),

                    "end": end_datetime.strftime(
                        "%H:%M"
                    ),

                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,

                    # Movement from previous
                    # 10-minute close
                    "points": net_points,

                    # Movement inside this block
                    "block_move": block_move,

                    # High-low movement
                    "range_points": range_points,

                    # Percentage movement
                    "swing_pct": swing_pct,
                    "block_pct": block_pct,
                    "range_pct": range_pct,

                    "direction": direction,

                    "volume": volume,
                }
            )

        return pd.DataFrame(rows)

    # =========================================================
    # SUMMARY
    # =========================================================

    @staticmethod
    def summarize(replay):
        """
        Generate complete historical-day summary.
        """

        if replay is None or replay.empty:

            return {
                "blocks": 0,
                "day_open": None,
                "day_high": None,
                "day_low": None,
                "day_close": None,
                "day_points": None,
                "day_range": None,
                "day_range_pct": None,
                "up_blocks": 0,
                "down_blocks": 0,
                "flat_blocks": 0,
                "biggest_move": None,
                "biggest_reversal": None,
            }

        # =====================================================
        # DAY OHLC
        # =====================================================

        day_open = float(
            replay.iloc[0]["open"]
        )

        day_close = float(
            replay.iloc[-1]["close"]
        )

        day_high = float(
            replay["high"].max()
        )

        day_low = float(
            replay["low"].min()
        )

        day_points = (
            day_close
            - day_open
        )

        day_range = (
            day_high
            - day_low
        )

        day_range_pct = (
            day_range
            / day_open
            * 100
            if day_open
            else 0.0
        )

        # =====================================================
        # BLOCK COUNTS
        # =====================================================

        up_blocks = int(
            (
                replay["direction"]
                == "UP"
            ).sum()
        )

        down_blocks = int(
            (
                replay["direction"]
                == "DOWN"
            ).sum()
        )

        flat_blocks = int(
            (
                replay["direction"]
                == "FLAT"
            ).sum()
        )

        # =====================================================
        # BIGGEST 10-MINUTE MOVE
        # =====================================================

        biggest_index = (
            replay["block_move"]
            .abs()
            .idxmax()
        )

        biggest = (
            replay.loc[
                biggest_index
            ]
            .to_dict()
        )

        # =====================================================
        # BIGGEST REVERSAL
        # =====================================================

        biggest_reversal = None

        for index in range(
            1,
            len(replay),
        ):

            previous = replay.iloc[
                index - 1
            ]

            current = replay.iloc[
                index
            ]

            previous_direction = (
                previous["direction"]
            )

            current_direction = (
                current["direction"]
            )

            if (
                previous_direction
                in ("UP", "DOWN")
                and current_direction
                in ("UP", "DOWN")
                and previous_direction
                != current_direction
            ):

                strength = (
                    abs(
                        float(
                            previous[
                                "block_move"
                            ]
                        )
                    )
                    +
                    abs(
                        float(
                            current[
                                "block_move"
                            ]
                        )
                    )
                )

                if (
                    biggest_reversal
                    is None
                    or strength
                    > biggest_reversal[
                        "_strength"
                    ]
                ):

                    biggest_reversal = {
                        "start": previous[
                            "start"
                        ],

                        "end": current[
                            "end"
                        ],

                        "from": previous[
                            "direction"
                        ],

                        "to": current[
                            "direction"
                        ],

                        "points": float(
                            current[
                                "block_move"
                            ]
                        ),

                        "_strength": strength,
                    }

        if biggest_reversal:
            biggest_reversal.pop(
                "_strength",
                None,
            )

        # =====================================================
        # FINAL SUMMARY
        # =====================================================

        return {
            "blocks": len(replay),

            "day_open": day_open,

            "day_high": day_high,

            "day_low": day_low,

            "day_close": day_close,

            "day_points": day_points,

            "day_range": day_range,

            "day_range_pct": day_range_pct,

            "up_blocks": up_blocks,

            "down_blocks": down_blocks,

            "flat_blocks": flat_blocks,

            "biggest_move": biggest,

            "biggest_reversal": biggest_reversal,
        }


# =============================================================
# SIMPLE PUBLIC FUNCTION
# =============================================================

def build_time_machine(
    smart_api,
    exchange,
    token,
    selected_date,
):
    """
    One-call interface for the Future Eye Time Machine.
    """

    engine = TimeMachineEngine(
        smart_api
    )

    candles = engine.fetch_day(
        exchange,
        token,
        selected_date,
    )

    replay = engine.build_replay(
        candles,
        selected_date,
    )

    summary = engine.summarize(
        replay
    )

    return {
        "candles": candles,
        "replay": replay,
        "summary": summary,
    }
