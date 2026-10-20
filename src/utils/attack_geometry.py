"""Attack reach measured from the detected player center, in frame pixels."""
def vertical_reach(config):
    total = max(0, int(config.get("range_y", 0)))
    return (max(0, int(config.get("range_up", total // 2))),
            max(0, int(config.get("range_down", total - total // 2))))
