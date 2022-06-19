from enum import Enum


class Role(Enum):
    FOLLOWER = 'Follower'
    CANDIDATE = 'Candidate'
    LEADER = 'Leader'
