from dataclasses import dataclass


@dataclass(slots=True)
class Round:
    game_no: str
    table_name: str

    winner: str

    banker_point: int
    player_point: int

    shoe_id: int | None = None
    round_no: int | None = None

    banker_cards: str | None = None
    player_cards: str | None = None