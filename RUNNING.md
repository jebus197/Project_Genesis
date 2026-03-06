# Running the Genesis Web Interface

## Prerequisites

- Python 3.9 or later
- pip (Python package installer)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jebus197/Project_Genesis.git
cd Project_Genesis

# Install the package with web dependencies
pip install -e ".[web]"

# Start the web server
python -m uvicorn genesis.web.app:create_app --factory --port 8111

# Open in browser
# http://localhost:8111
```

## What You Will See

The Genesis web interface runs in **proof-of-concept mode** with demonstration data. Everything is functional — pages, navigation, storyboard, mission lifecycle, circles, assembly, audit trail — but the data is seeded for demonstration purposes. Real missions begin at First Light.

### Key Pages

| URL | What It Shows |
|-----|---------------|
| `/` | Landing page and social feed |
| `/about/story` | 18-step walkthrough (start here for the full Genesis story) |
| `/missions` | Mission board — browse, create, bid |
| `/circles` | Constitutional and working circles |
| `/assembly` | Governance assembly and amendment paths |
| `/audit` | Audit trail and constitutional event log |
| `/members` | Member dashboard (trust, rewards, GCF allocation) |
| `/about` | Deep FAQ — constitutional depth on every topic |

### The Storyboard

Navigate to `/about/story` for the complete Genesis walkthrough. It is a linear 18-step click-through covering:

1. **Why Genesis** (steps 1–3): The problem, the intellectual heritage, why anti-social
2. **How Genesis Works** (steps 4–7): Mission lifecycle, verification, trust, rewards
3. **How To Participate** (steps 8–11): Joining, circles, governance, your dashboard
4. **The Road Ahead** (steps 12–18): First Light, epochs, distributed compute, coexistence, distributed immunity, verifiability, the founder's horizon

Every deep link in the storyboard goes to a real, functional page.

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[web,dev]"

# Run the full test suite
python -m pytest tests/ -q
```

## Notes

- No database required — the PoC runs entirely in-memory with seeded data
- No API keys, no external services, no configuration files needed
- The server runs on port 8111 by default (change with `--port`)
- Add `--reload` for auto-restart during development
- JSON API: add `Accept: application/json` header to any route for machine-readable output
