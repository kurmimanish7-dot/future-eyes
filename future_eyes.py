"""
Future Eyes
===========

Historical future-vision research engine.

Purpose:
    Reconstruct what Future Eyes could have known at a specific
    historical checkpoint and evaluate what happened afterward.

IMPORTANT:
    - Paper-trading research only.
    - No real orders.
    - Future candles are NEVER included in the decision dataset.
    - Actual future candles are used only AFTER the decision is made
      for validation/scoring.

Works with:
    time_machine_engine.py
"""

from datetime import datetime, timedelta

import pandas as pd


class FutureEyesEngine:
    """
    Future Eyes historical checkpoint engine.

    Example:

        09:25 checkpoint
            ↓
        Data available until 09:25
            ↓
        Decision
            ↓
        09:25 → 09:35 candle
            ↓
        Actual result
    """

    def __init__(
        self,
        time_machine,
        checkpoint_minutes=10,
    ):
        self.time_machine = time_machine
        self.checkpoint_minutes = int(
            checkpoint_minutes
        )

    # =========================================================
    # EMPTY RESULT
    # =========================================================

    @staticmethod
    def _empty_result():

        return {
            "checkpoint": None,
            "available_data": pd.DataFrame(),
            "future_data": pd.DataFrame(),
            "decision": None,
            "actual_result": None,
        }

    # =========================================================
    # NORMALIZE DATA
    # =========================================================

    @staticmethod
    def _prepare_replay(replay):

        if replay is None:
            return pd.DataFrame()

        if not isinstance(
            replay,
            pd.DataFrame,
        ):
            return pd.DataFrame()

        if replay.empty:
            return pd.DataFrame()

        df = replay.copy()

        if "start" not in df.columns:
            return pd.DataFrame()

        df["_start_time"] = pd.to_datetime(
            df["start"],
            format="%H:%M",
            errors="coerce",
        )

        df = df.dropna(
            subset=["_start_time"]
        )

        return df.reset_index(drop=True)

    # =========================================================
    # CHECKPOINTS
    # =========================================================

    def build_checkpoints(
        self,
        replay,
    ):
        """
        Build historical decision checkpoints.

        A checkpoint represents the point where Future Eyes
        is allowed to make a decision.

        Future candles are not included.
        """

        df = self._prepare_replay(
            replay
        )

        if df.empty:
            return []

        checkpoints = []

        for index in range(
            len(df)
        ):

            candle = df.iloc[index]

            checkpoints.append(
                {
                    "index": index,

                    "checkpoint": candle[
                        "start"
                    ],

                    "next_checkpoint": (
                        candle["end"]
                        if "end" in df.columns
                        else None
                    ),

                    "available_until": candle[
                        "end"
                    ]
                    if "end" in df.columns
                    else candle["start"],
                }
            )

        return checkpoints

    # =========================================================
    # HISTORICAL INFORMATION SET
    # =========================================================

    def get_available_data(
        self,
        replay,
        checkpoint_index,
    ):
        """
        Return ONLY data available at the checkpoint.

        The current block is considered available only after
        its close.

        Therefore the decision for the next block uses data
        from completed blocks only.
        """

        df = self._prepare_replay(
            replay
        )

        if df.empty:
            return pd.DataFrame()

        if checkpoint_index <= 0:
            return pd.DataFrame(
                columns=df.columns
            )

        checkpoint_index = min(
            int(checkpoint_index),
            len(df),
        )

        available = df.iloc[
            :checkpoint_index
        ].copy()

        return available.reset_index(
            drop=True
        )

    # =========================================================
    # FUTURE DATA
    # =========================================================

    def get_future_data(
        self,
        replay,
        checkpoint_index,
    ):
        """
        Return data AFTER the decision point.

        This method is ONLY for validation.

        It must NEVER be passed into the decision engine.
        """

        df = self._prepare_replay(
            replay
        )

        if df.empty:
            return pd.DataFrame()

        checkpoint_index = max(
            0,
            int(checkpoint_index),
        )

        future = df.iloc[
            checkpoint_index:
        ].copy()

        return future.reset_index(
            drop=True
        )

    # =========================================================
    # NEXT BLOCK RESULT
    # =========================================================

    @staticmethod
    def evaluate_next_block(
        future_data,
    ):
        """
        Evaluate the immediate next historical block.

        Used only after the decision has been generated.
        """

        if (
            future_data is None
            or future_data.empty
        ):
            return None

        row = future_data.iloc[0]

        return {
            "start": row.get(
                "start"
            ),

            "end": row.get(
                "end"
            ),

            "open": float(
                row["open"]
            ),

            "high": float(
                row["high"]
            ),

            "low": float(
                row["low"]
            ),

            "close": float(
                row["close"]
            ),

            "points": float(
                row.get(
                    "points",
                    0,
                )
            ),

            "block_move": float(
                row.get(
                    "block_move",
                    0,
                )
            ),

            "direction": row.get(
                "direction"
            ),
        }

    # =========================================================
    # SCORE DECISION
    # =========================================================

    @staticmethod
    def score_decision(
        decision,
        actual_result,
    ):
        """
        Compare a historical decision with the actual
        next-block movement.

        Supported decisions:

            BUY
            SELL
            LONG
            SHORT
            UP
            DOWN
            HOLD
            NO TRADE
            WAIT
        """

        if not decision:
            return {
                "status": "NO_DECISION",
                "points": 0.0,
            }

        if not actual_result:
            return {
                "status": "NO_FUTURE_DATA",
                "points": 0.0,
            }

        action = str(
            decision
        ).strip().upper()

        actual_move = float(
            actual_result.get(
                "block_move",
                0,
            )
        )

        if action in (
            "BUY",
            "LONG",
            "UP",
        ):

            if actual_move > 0:
                return {
                    "status": "WIN",
                    "points": actual_move,
                }

            if actual_move < 0:
                return {
                    "status": "LOSS",
                    "points": actual_move,
                }

            return {
                "status": "FLAT",
                "points": 0.0,
            }

        if action in (
            "SELL",
            "SHORT",
            "DOWN",
        ):

            if actual_move < 0:
                return {
                    "status": "WIN",
                    "points": abs(
                        actual_move
                    ),
                }

            if actual_move > 0:
                return {
                    "status": "LOSS",
                    "points": actual_move,
                }

            return {
                "status": "FLAT",
                "points": 0.0,
            }

        return {
            "status": "NO_TRADE",
            "points": 0.0,
        }

    # =========================================================
    # RUN ONE CHECKPOINT
    # =========================================================

    def run_checkpoint(
        self,
        replay,
        checkpoint_index,
        decision=None,
    ):
        """
        Run one Future Eyes checkpoint.

        IMPORTANT:

        decision must be generated from available_data ONLY.

        future_data is returned separately for validation.
        """

        df = self._prepare_replay(
            replay
        )

        if df.empty:
            return self._empty_result()

        if checkpoint_index <= 0:
            return self._empty_result()

        if checkpoint_index >= len(df):
            return {
                "checkpoint": None,
                "available_data": df.copy(),
                "future_data": pd.DataFrame(),
                "decision": decision,
                "actual_result": None,
                "score": {
                    "status": "NO_FUTURE_DATA",
                    "points": 0.0,
                },
            }

        available_data = (
            self.get_available_data(
                df,
                checkpoint_index,
            )
        )

        future_data = (
            self.get_future_data(
                df,
                checkpoint_index,
            )
        )

        actual_result = (
            self.evaluate_next_block(
                future_data
            )
        )

        score = self.score_decision(
            decision,
            actual_result,
        )

        checkpoint = df.iloc[
            checkpoint_index - 1
        ]

        return {
            "checkpoint": checkpoint.get(
                "end"
            ),

            "available_data": available_data,

            # Kept separate intentionally.
            # Never use this for decision generation.
            "future_data": future_data,

            "decision": decision,

            "actual_result": actual_result,

            "score": score,
        }

    # =========================================================
    # RUN FULL HISTORICAL DAY
    # =========================================================

    def run_day(
        self,
        replay,
        decision_function=None,
    ):
        """
        Run Future Eyes across the entire historical day.

        decision_function receives ONLY:

            available_data

        It must return one of:

            BUY
            SELL
            HOLD
            WAIT
            NO TRADE

        Future data is never passed to decision_function.
        """

        df = self._prepare_replay(
            replay
        )

        if df.empty:
            return pd.DataFrame()

        results = []

        for checkpoint_index in range(
            1,
            len(df),
        ):

            available_data = (
                self.get_available_data(
                    df,
                    checkpoint_index,
                )
            )

            decision = None

            if decision_function:
                try:
                    decision = (
                        decision_function(
                            available_data
                        )
                    )
                except Exception:
                    decision = None

            result = self.run_checkpoint(
                replay=df,
                checkpoint_index=checkpoint_index,
                decision=decision,
            )

            actual = result.get(
                "actual_result"
            ) or {}

            score = result.get(
                "score"
            ) or {}

            results.append(
                {
                    "checkpoint": result.get(
                        "checkpoint"
                    ),

                    "decision": decision,

                    "actual_direction": actual.get(
                        "direction"
                    ),

                    "actual_points": actual.get(
                        "points"
                    ),

                    "status": score.get(
                        "status"
                    ),

                    "score_points": score.get(
                        "points"
                    ),
                }
            )

        return pd.DataFrame(
            results
        )

    # =========================================================
    # SUMMARY
    # =========================================================

    @staticmethod
    def summarize_results(
        results,
    ):
        """
        Summarize Future Eyes historical performance.
        """

        if (
            results is None
            or results.empty
        ):
            return {
                "checkpoints": 0,
                "wins": 0,
                "losses": 0,
                "flat": 0,
                "no_trade": 0,
                "accuracy": 0.0,
                "points": 0.0,
            }

        wins = int(
            (
                results["status"]
                == "WIN"
            ).sum()
        )

        losses = int(
            (
                results["status"]
                == "LOSS"
            ).sum()
        )

        flat = int(
            (
                results["status"]
                == "FLAT"
            ).sum()
        )

        no_trade = int(
            (
                results["status"]
                == "NO_TRADE"
            ).sum()
        )

        decided = wins + losses

        accuracy = (
            wins / decided * 100
            if decided
            else 0.0
        )

        points = float(
            pd.to_numeric(
                results["score_points"],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )

        return {
            "checkpoints": len(
                results
            ),

            "wins": wins,

            "losses": losses,

            "flat": flat,

            "no_trade": no_trade,

            "accuracy": accuracy,

            "points": points,
        }


# =============================================================
# SIMPLE PUBLIC FUNCTION
# =============================================================

def create_future_eyes(
    time_machine,
    replay,
):
    """
    Create a Future Eyes engine for an existing replay.
    """

    return FutureEyesEngine(
        time_machine=time_machine,
        checkpoint_minutes=10,
    )
