def update_state(
    ball_position: tuple[int, int],
    target_position: tuple[int, int],
    settings: tuple[float, float, float],
) -> None:
    """Receive grid positions and normalized slider settings for the MPC."""
    print(
        f"MPC input: ball={ball_position}, target={target_position}, "
        f"settings={settings}"
    )
