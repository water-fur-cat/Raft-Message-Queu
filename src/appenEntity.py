from dataclasses import dataclass


@dataclass
class AppendEntity:
    type: str
    entityId: int

    term: int
    leaderId: int
    leaderPort: str

    prevLogIndex: int
    prevLogTerm: int

    recipientPort: str
    agree: bool
    leaderCommit: bool

    entry: str
