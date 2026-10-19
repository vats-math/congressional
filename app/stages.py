"""Shared vocabulary for the v3 data: pathway stages, environment tags, weekdays.

Everything that validates or scores programs imports from here, so there is
exactly one place to add a stage or a tag.
"""
from __future__ import annotations

# Ordered from first step to most competitive. The pathway engine walks this order.
STAGES = (
    "intro_clinic",
    "open_play",
    "camp",
    "rec_league",
    "intermediate_group",
    "school_team",
    "club_league",
)

STAGE_LABELS = {
    "intro_clinic": "Intro clinic",
    "open_play": "Open play",
    "camp": "Camp",
    "rec_league": "Recreational league",
    "intermediate_group": "Intermediate group",
    "school_team": "School team",
    "club_league": "Club league",
}

# What the environment of a program feels like. The barrier detector (Phase 5)
# boosts or avoids these tags, so keep the list short and meaningful.
ENVIRONMENT_TAGS = (
    "beginner_friendly",
    "drop_in",
    "girls_only",
    "no_tryouts",
    "tryout_required",
    "parent_required",
    "free_or_aid",
    "adaptive",
)

# Monday = 0 ... Sunday = 6, the same numbering as datetime.date.weekday().
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
