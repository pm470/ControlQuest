def update_state(
    ball_position: tuple[int, int],
    target_position: tuple[int, int],
) -> None:
    """Receive the current and desired grid cells for the MPC integration."""
    print(
        f"MPC input: ball={ball_position}, target={target_position}"
    )
