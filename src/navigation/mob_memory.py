"""Remember remote destinations; live detections still decide attacks."""


class PlatformMobMemory:
    def __init__(self):
        self.targets = {}
        self.current = None
        self.last_survey = -100.0

    def arrive(self, platform):
        if platform is not None:
            self.current = platform
            self.targets.pop(platform, None)

    def remember(self, targets, here):
        for target in targets:
            if target['platform'] != here:
                self.targets[target['platform']] = dict(target)

    def needs_survey(self, now):
        return not self.targets and now-self.last_survey >= 3.0
