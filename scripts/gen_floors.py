"""Generate the demo floor plans (frontend/public/floors.json).

Replace this with your real floor plans: each floor is an SVG-coordinate
canvas with zones (rectangles) and desks (points). Admins can edit the JSON
directly; desk IDs must match the `desk` column in data/people.csv.
"""
import json
from pathlib import Path


def desk_grid(prefix, zone_id, x0, y0, cols, rows, dx=78, dy=90):
    desks = []
    n = 1
    for r in range(rows):
        for c in range(cols):
            desks.append({"id": f"{prefix}-{n:02d}", "x": x0 + c * dx, "y": y0 + r * dy, "zone": zone_id})
            n += 1
    return desks


floors = [
    {
        "id": "L5", "name": "Level 5", "width": 1000, "height": 600,
        "zones": [
            {"id": "Atlas Zone", "x": 40, "y": 60, "w": 440, "h": 250, "color": "#2f6fed"},
            {"id": "Design Studio", "x": 520, "y": 60, "w": 230, "h": 250, "color": "#b04ad6"},
            {"id": "People Ops", "x": 780, "y": 60, "w": 180, "h": 250, "color": "#e0752d"},
            {"id": "Collab Hub", "x": 40, "y": 350, "w": 440, "h": 210, "color": "#1f9d74", "amenity": True},
            {"id": "Pantry", "x": 520, "y": 350, "w": 440, "h": 210, "color": "#8a8f98", "amenity": True},
        ],
        "desks": desk_grid("5-A", "Atlas Zone", 90, 130, 5, 2)
        + desk_grid("5-C", "Design Studio", 580, 130, 2, 2, dx=110)
        + desk_grid("5-D", "People Ops", 830, 130, 2, 2, dx=80),
    },
    {
        "id": "L6", "name": "Level 6", "width": 1000, "height": 600,
        "zones": [
            {"id": "Platform Zone", "x": 40, "y": 60, "w": 440, "h": 250, "color": "#2f6fed"},
            {"id": "Insights Zone", "x": 520, "y": 60, "w": 440, "h": 250, "color": "#1f9d74"},
            {"id": "War Room", "x": 40, "y": 350, "w": 300, "h": 210, "color": "#c43b3b", "amenity": True},
            {"id": "Quiet Pods", "x": 380, "y": 350, "w": 580, "h": 210, "color": "#8a8f98", "amenity": True},
        ],
        "desks": desk_grid("6-A", "Platform Zone", 90, 130, 5, 2)
        + desk_grid("6-B", "Insights Zone", 570, 130, 5, 2),
    },
    {
        # Meeting-room floor. Room zones have type "room" and a roomId matching
        # backend/src/beacon/data/rooms.json; the app colours them free / occupied.
        "id": "L9", "name": "Level 9", "width": 1000, "height": 600,
        "zones": [
            {"id": "St John", "x": 40, "y": 60, "w": 380, "h": 250, "color": "#2f6fed", "type": "room", "roomId": "st-john"},
            {"id": "Lazarus", "x": 440, "y": 60, "w": 260, "h": 250, "color": "#2f6fed", "type": "room", "roomId": "lazarus"},
            {"id": "Seringat", "x": 720, "y": 60, "w": 240, "h": 250, "color": "#2f6fed", "type": "room", "roomId": "seringat"},
            {"id": "Kusu", "x": 40, "y": 350, "w": 200, "h": 210, "color": "#2f6fed", "type": "room", "roomId": "kusu"},
            {"id": "Reception", "x": 260, "y": 350, "w": 300, "h": 210, "color": "#8a8f98", "amenity": True},
            {"id": "Pantry", "x": 580, "y": 350, "w": 380, "h": 210, "color": "#8a8f98", "amenity": True},
        ],
        "desks": [],
    },
]

out = Path(__file__).resolve().parent.parent / "frontend" / "public" / "floors.json"
out.write_text(json.dumps({"floors": floors}, indent=2))
print(f"wrote {out}")
