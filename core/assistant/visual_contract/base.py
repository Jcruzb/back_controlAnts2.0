from copy import deepcopy

from core.assistant.visual_contract.enums import BLOCK_VERSION


class VisualBlock:
    version = BLOCK_VERSION
    block_type = None

    @classmethod
    def validate(cls, payload):
        raise NotImplementedError

    @classmethod
    def create(cls, payload):
        cls.validate(payload)
        return deepcopy(payload)
