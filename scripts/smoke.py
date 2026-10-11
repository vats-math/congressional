import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import fetch_all, init_db
from app.parser import parse_query
from app.ranking import rank_catalog
from app.analysis import analyze

init_db()
profile = parse_query(
    "I'm 14, play recreational soccer and want to find travel opportunities near Dallas"
)
ranked = rank_catalog(profile, fetch_all())
print(profile)
print(ranked[0]["name"], ranked[0]["compatibility"], ranked[0]["city"])
print(analyze(ranked)["mean_score"], "n=", len(ranked))
