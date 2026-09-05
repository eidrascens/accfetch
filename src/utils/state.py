def load_state(state_file: str) -> Dict[str, Any]:
    """Load state from JSON file."""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception:
            logger.warning(
                f"Could not read state file {state_file}, starting fresh.")
    return {}


def save_state(state_file: str, state: Dict[str, Any]) -> None:
    """Save state to JSON file atomically."""
    tmp_file = state_file + ".tmp"
    with open(tmp_file, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)


def update_state(
    state: Dict[str, Any],
    srr: str,
    key: str,
    value: bool = True,
) -> None:
    """Update state for a given SRR."""
    if srr not in state:
        state[srr] = {}
    state[srr][key] = value


def get_state(state: Dict[str, Any], srr: str, key: str, default: bool = False) -> bool:
    """Get state value for SRR and key."""
    return state.get(srr, {}).get(key, default)
